//! Linkage source for wallet grouping (Rust mirror of `api/account/linkage.py`).
//!
//! Resolves the set of wallets linked to an address by querying the Silk
//! auth-server's public read endpoint, behind a 60s freshness cache and a
//! killswitch. Phase 3b of the wallet-linking → Silk migration (#589).
//!
//! Behaviour mirrors the Python path: `LINKED_WALLETS_SOURCE_ENABLED` gates the
//! Silk call; a successful (including empty) response is cached for 60s; an empty
//! response means "no linkage" and resolves to the solo set; on any Silk failure
//! we never poison the cache — we serve the last good value if we have one,
//! otherwise fall back to solo.

use std::collections::{BTreeSet, HashMap};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use serde::Deserialize;
use sqlx::PgPool;
use tracing::warn;

use crate::db::DatabaseError;

/// Freshness window for a successful lookup.
const CACHE_TTL: Duration = Duration::from_secs(60);
/// How long a cached value may still be served when Silk is failing. Matches
/// Python's `LAST_GOOD_TTL`, so an outage can't keep a long-gone group alive.
const LAST_GOOD_TTL: Duration = Duration::from_secs(60 * 60);
/// Most entries the in-process cache keeps. Past it, entries older than
/// `LAST_GOOD_TTL` are dropped, and if that isn't enough the cache is cleared.
const MAX_CACHE_ENTRIES: usize = 50_000;
/// Per-request Silk timeout. Scoring is latency-sensitive; fail fast.
const REQUEST_TIMEOUT: Duration = Duration::from_secs(2);

struct SilkConfig {
    enabled: bool,
    base_url: String,
    service_key: String,
}

fn silk_config() -> &'static SilkConfig {
    static CONFIG: OnceLock<SilkConfig> = OnceLock::new();
    CONFIG.get_or_init(|| SilkConfig {
        enabled: std::env::var("LINKED_WALLETS_SOURCE_ENABLED")
            // Mirror django-environ's BOOLEAN_TRUE_STRINGS so the killswitch reads
            // identically across the Python and Rust scorers.
            .map(|v| {
                matches!(
                    v.trim().to_lowercase().as_str(),
                    "true" | "on" | "ok" | "y" | "yes" | "1"
                )
            })
            .unwrap_or(false),
        base_url: std::env::var("SILK_AUTH_SERVER_URL").unwrap_or_default(),
        service_key: std::env::var("SILK_SERVICE_API_KEY").unwrap_or_default(),
    })
}

fn http_client() -> &'static reqwest::Client {
    static CLIENT: OnceLock<reqwest::Client> = OnceLock::new();
    CLIENT.get_or_init(reqwest::Client::new)
}

/// `address -> (linked set, fetched_at)`. An entry is fresh for `CACHE_TTL` and
/// serves as the stale-on-failure value for `LAST_GOOD_TTL`. Size is capped at
/// `MAX_CACHE_ENTRIES` (see `insert_bounded`).
type LinkedCache = Mutex<HashMap<String, (Vec<String>, Instant)>>;

fn cache() -> &'static LinkedCache {
    static CACHE: OnceLock<LinkedCache> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

#[derive(Deserialize)]
struct SilkResponse {
    #[serde(default)]
    addresses: Vec<String>,
}

/// Return all addresses linked to `address` (always lowercased).
///
/// Returns `[address]` when the killswitch is off, when Silk reports no linkage,
/// or when Silk is unreachable and no cached value exists. The `_pool` argument
/// is unused (the cache layer handles fallback) but kept so the call site in
/// `domain::scoring` is unchanged. Always returns `Ok` — failures degrade to the
/// solo set rather than surfacing as errors.
pub async fn get_linked_addresses(
    address: &str,
    _pool: &PgPool,
) -> Result<Vec<String>, DatabaseError> {
    let address = address.to_lowercase();
    Ok(fetch_linked(&address, silk_config(), http_client(), cache(), CACHE_TTL).await)
}

/// Core resolution logic, parameterized over its dependencies so tests can
/// inject a mock Silk server, a fresh client, an isolated cache, and a custom
/// freshness window. `address` is assumed already lowercased.
async fn fetch_linked(
    address: &str,
    config: &SilkConfig,
    client: &reqwest::Client,
    cache: &LinkedCache,
    ttl: Duration,
) -> Vec<String> {
    let solo = vec![address.to_string()];

    if !config.enabled {
        return solo;
    }

    // The address goes into the Silk URL path, sent with the service key, so
    // only a plain EVM address may reach it (Silk applies the same rule).
    if !is_evm_address(address) {
        warn!("linked wallets: not an EVM address, treating as solo: {address:?}");
        return solo;
    }

    // Fresh cache hit: serve without calling Silk.
    if let Some((value, fetched_at)) = cache.lock().unwrap().get(address) {
        if fetched_at.elapsed() < ttl {
            return value.clone();
        }
    }

    match fetch_from_silk(address, config, client).await {
        Ok(raw) => {
            let normalized = normalize(raw, address);
            insert_bounded(&mut cache.lock().unwrap(), address, normalized.clone());
            normalized
        }
        Err(err) => {
            // No-poison: never write the cache on failure. Serve the last good
            // value if it is recent enough, else fall back to solo.
            let last_good = cache.lock().unwrap().get(address)
                .filter(|(_, fetched_at)| fetched_at.elapsed() < LAST_GOOD_TTL)
                .map(|(value, _)| value.clone());
            if let Some(value) = last_good {
                warn!("linked wallets: Silk fetch failed for {address}, serving stale value ({err})");
                value
            } else {
                warn!("linked wallets: Silk fetch failed for {address} with no recent cached value, falling back to solo ({err})");
                solo
            }
        }
    }
}

/// GET the linked-wallet cluster for `address`. Non-2xx responses and transport
/// errors surface as `Err` so the caller can apply its fallback policy.
async fn fetch_from_silk(
    address: &str,
    config: &SilkConfig,
    client: &reqwest::Client,
) -> Result<Vec<String>, reqwest::Error> {
    let url = format!(
        "{}/api/public/linked-wallets/by-address/{}",
        config.base_url, address
    );
    let body: SilkResponse = client
        .get(&url)
        .header("X-Service-Key", &config.service_key)
        .timeout(REQUEST_TIMEOUT)
        .send()
        .await?
        .error_for_status()?
        .json()
        .await?;
    Ok(body.addresses)
}

/// `0x` followed by 40 lowercase hex characters (the address is lowercased first).
fn is_evm_address(address: &str) -> bool {
    address.len() == 42
        && address.starts_with("0x")
        && address[2..].bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
}

/// Insert a fresh entry, keeping the cache under `MAX_CACHE_ENTRIES`.
fn insert_bounded(cache: &mut HashMap<String, (Vec<String>, Instant)>, address: &str, value: Vec<String>) {
    if cache.len() >= MAX_CACHE_ENTRIES && !cache.contains_key(address) {
        cache.retain(|_, (_, fetched_at)| fetched_at.elapsed() < LAST_GOOD_TTL);
        if cache.len() >= MAX_CACHE_ENTRIES {
            cache.clear();
        }
    }
    cache.insert(address.to_string(), (value, Instant::now()));
}

/// Lowercase, dedupe, guarantee `address` is present, and sort lexically.
fn normalize(addresses: Vec<String>, address: &str) -> Vec<String> {
    let mut cluster: BTreeSet<String> = addresses.into_iter().map(|a| a.to_lowercase()).collect();
    cluster.insert(address.to_string());
    cluster.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use wiremock::matchers::{header, method, path};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    fn config(base_url: String, enabled: bool) -> SilkConfig {
        SilkConfig {
            enabled,
            base_url,
            service_key: "svc-key".to_string(),
        }
    }

    fn empty_cache() -> LinkedCache {
        Mutex::new(HashMap::new())
    }

    async fn mount_addresses(server: &MockServer, addr: &str, addresses: serde_json::Value) {
        Mock::given(method("GET"))
            .and(path(format!("/api/public/linked-wallets/by-address/{addr}")))
            .and(header("X-Service-Key", "svc-key"))
            .respond_with(ResponseTemplate::new(200).set_body_json(json!({ "addresses": addresses })))
            .mount(server)
            .await;
    }

    #[tokio::test]
    async fn killswitch_off_returns_solo_without_request() {
        let server = MockServer::start().await;
        let cache = empty_cache();

        let result = fetch_linked(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            &config(server.uri(), false),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string()]);
        assert_eq!(server.received_requests().await.unwrap().len(), 0);
    }

    #[tokio::test]
    async fn happy_path_normalizes_and_caches() {
        let server = MockServer::start().await;
        mount_addresses(&server, "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", json!(["0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC", "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"])).await;
        let cache = empty_cache();

        let result = fetch_linked(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "0xcccccccccccccccccccccccccccccccccccccccc"]);
        assert!(cache.lock().unwrap().contains_key("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"));
    }

    #[tokio::test]
    async fn empty_response_returns_solo() {
        let server = MockServer::start().await;
        mount_addresses(&server, "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", json!([])).await;
        let cache = empty_cache();

        let result = fetch_linked(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string()]);
    }

    #[tokio::test]
    async fn cache_hit_skips_second_request() {
        let server = MockServer::start().await;
        mount_addresses(&server, "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", json!(["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"])).await;
        let cache = empty_cache();
        let cfg = config(server.uri(), true);
        let client = reqwest::Client::new();

        fetch_linked("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", &cfg, &client, &cache, CACHE_TTL).await;
        fetch_linked("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", &cfg, &client, &cache, CACHE_TTL).await;

        assert_eq!(server.received_requests().await.unwrap().len(), 1);
    }

    #[tokio::test]
    async fn failure_with_stale_cache_serves_stale() {
        let server = MockServer::start().await;
        Mock::given(method("GET"))
            .respond_with(ResponseTemplate::new(503))
            .mount(&server)
            .await;
        let cache = empty_cache();
        cache.lock().unwrap().insert(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string(),
            (vec!["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string(), "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb".to_string()], Instant::now()),
        );

        // ttl = ZERO forces the existing entry to be treated as expired, so we
        // reach the fetch (which 503s) and fall back to the stale value.
        let result = fetch_linked(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            Duration::ZERO,
        )
        .await;

        assert_eq!(result, vec!["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]);
    }

    #[tokio::test]
    async fn non_address_never_reaches_silk() {
        let server = MockServer::start().await;
        Mock::given(method("GET"))
            .respond_with(ResponseTemplate::new(200).set_body_json(json!({ "addresses": ["0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"] })))
            .mount(&server)
            .await;
        let cfg = config(server.uri(), true);
        let client = reqwest::Client::new();
        let long = format!("0x{}", "a".repeat(40));

        for address in ["../../admin".to_string(), format!("0x{}", "a".repeat(39)), "a".repeat(40),
                        format!("{long}/../x"), format!("{long}\n"), format!("0x{}", "g".repeat(40))] {
            let cache = empty_cache();
            let result = fetch_linked(&address, &cfg, &client, &cache, CACHE_TTL).await;
            assert_eq!(result, vec![address.clone()], "{address:?}");
        }
        assert_eq!(server.received_requests().await.unwrap().len(), 0);
    }

    #[tokio::test]
    async fn failure_with_expired_last_good_returns_solo() {
        let server = MockServer::start().await;
        Mock::given(method("GET"))
            .respond_with(ResponseTemplate::new(503))
            .mount(&server)
            .await;
        let cache = empty_cache();
        let Some(long_ago) = Instant::now().checked_sub(LAST_GOOD_TTL + Duration::from_secs(1)) else {
            return; // Clock too close to boot to build an old Instant.
        };
        cache.lock().unwrap().insert(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string(),
            (vec!["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string(), "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb".to_string()], long_ago),
        );

        let result = fetch_linked(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string()]);
    }

    #[test]
    fn insert_bounded_caps_the_cache() {
        let mut cache = HashMap::new();
        for i in 0..MAX_CACHE_ENTRIES {
            cache.insert(format!("0x{i:040x}"), (Vec::new(), Instant::now()));
        }
        insert_bounded(&mut cache, "0xnew", vec!["0xnew".to_string()]);
        assert!(cache.len() <= MAX_CACHE_ENTRIES);
        assert!(cache.contains_key("0xnew"));

        // Refreshing an existing key never evicts others.
        let mut small = HashMap::new();
        insert_bounded(&mut small, "0xa", Vec::new());
        insert_bounded(&mut small, "0xa", Vec::new());
        assert_eq!(small.len(), 1);
    }

    #[tokio::test]
    async fn failure_with_cold_cache_returns_solo() {
        let server = MockServer::start().await;
        Mock::given(method("GET"))
            .respond_with(ResponseTemplate::new(503))
            .mount(&server)
            .await;
        let cache = empty_cache();

        let result = fetch_linked(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string()]);
    }

    #[tokio::test]
    async fn failure_does_not_poison_cache() {
        let server = MockServer::start().await;
        Mock::given(method("GET"))
            .respond_with(ResponseTemplate::new(503))
            .mount(&server)
            .await;
        let cache = empty_cache();

        fetch_linked(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert!(cache.lock().unwrap().is_empty());
    }
}
