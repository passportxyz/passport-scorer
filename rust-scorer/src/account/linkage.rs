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

/// `address -> (linked set, fetched_at)`. In-process entries never auto-expire,
/// so an entry doubles as both the freshness check and the stale-on-failure
/// source. The address space per process is bounded; a future revision could
/// swap this for `moka` with TTL eviction if memory becomes a concern.
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

    // Fresh cache hit: serve without calling Silk.
    if let Some((value, fetched_at)) = cache.lock().unwrap().get(address) {
        if fetched_at.elapsed() < ttl {
            return value.clone();
        }
    }

    match fetch_from_silk(address, config, client).await {
        Ok(raw) => {
            let normalized = normalize(raw, address);
            cache
                .lock()
                .unwrap()
                .insert(address.to_string(), (normalized.clone(), Instant::now()));
            normalized
        }
        Err(err) => {
            // No-poison: never write the cache on failure. Serve the last good
            // value if present, else fall back to solo.
            if let Some((value, _)) = cache.lock().unwrap().get(address) {
                warn!("linked wallets: Silk fetch failed for {address}, serving stale value ({err})");
                value.clone()
            } else {
                warn!("linked wallets: Silk fetch failed for {address} with no cached value, falling back to solo ({err})");
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
            "0xaaa",
            &config(server.uri(), false),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaa".to_string()]);
        assert_eq!(server.received_requests().await.unwrap().len(), 0);
    }

    #[tokio::test]
    async fn happy_path_normalizes_and_caches() {
        let server = MockServer::start().await;
        mount_addresses(&server, "0xaaa", json!(["0xCCC", "0xAAA", "0xBBB", "0xbbb"])).await;
        let cache = empty_cache();

        let result = fetch_linked(
            "0xaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaa", "0xbbb", "0xccc"]);
        assert!(cache.lock().unwrap().contains_key("0xaaa"));
    }

    #[tokio::test]
    async fn empty_response_returns_solo() {
        let server = MockServer::start().await;
        mount_addresses(&server, "0xaaa", json!([])).await;
        let cache = empty_cache();

        let result = fetch_linked(
            "0xaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaa".to_string()]);
    }

    #[tokio::test]
    async fn cache_hit_skips_second_request() {
        let server = MockServer::start().await;
        mount_addresses(&server, "0xaaa", json!(["0xaaa", "0xbbb"])).await;
        let cache = empty_cache();
        let cfg = config(server.uri(), true);
        let client = reqwest::Client::new();

        fetch_linked("0xaaa", &cfg, &client, &cache, CACHE_TTL).await;
        fetch_linked("0xaaa", &cfg, &client, &cache, CACHE_TTL).await;

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
            "0xaaa".to_string(),
            (vec!["0xaaa".to_string(), "0xbbb".to_string()], Instant::now()),
        );

        // ttl = ZERO forces the existing entry to be treated as expired, so we
        // reach the fetch (which 503s) and fall back to the stale value.
        let result = fetch_linked(
            "0xaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            Duration::ZERO,
        )
        .await;

        assert_eq!(result, vec!["0xaaa", "0xbbb"]);
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
            "0xaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert_eq!(result, vec!["0xaaa".to_string()]);
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
            "0xaaa",
            &config(server.uri(), true),
            &reqwest::Client::new(),
            &cache,
            CACHE_TTL,
        )
        .await;

        assert!(cache.lock().unwrap().is_empty());
    }
}
