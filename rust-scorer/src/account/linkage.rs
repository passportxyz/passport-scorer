//! Linkage source for wallet grouping (Rust mirror of `api/account/linkage.py`).
//!
//! Phase 0 stub: solo set only. Phase 3b (#589) replaces with a Silk fetch +
//! SWR cache + `LINKED_WALLETS_SOURCE_ENABLED` killswitch +
//! `scorer.linked_wallets.fallback_to_solo` metric.

use sqlx::PgPool;

use crate::db::DatabaseError;

/// Return all addresses linked to `address`.
///
/// Phase 0 stub: returns just the solo address (lowercased). The `_pool`
/// argument is unused in the stub but kept so the signature matches what
/// Phase 3b needs (Silk HTTP call with DB-backed fallback metadata).
pub async fn get_linked_addresses(
    address: &str,
    _pool: &PgPool,
) -> Result<Vec<String>, DatabaseError> {
    Ok(vec![address.to_lowercase()])
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, serde::Deserialize)]
pub struct WalletIdentity {
    pub address: String,
    #[serde(rename = "chainId")]
    pub chain_id: Option<i64>,
}

impl WalletIdentity {
    pub fn key(&self) -> String {
        match self.chain_id {
            Some(chain_id) => format!("eip155:{chain_id}:{}", self.address),
            None => self.address.clone(),
        }
    }
}

#[derive(serde::Deserialize)]
struct SilkWalletCluster {
    wallets: Vec<WalletIdentity>,
    #[serde(rename = "waapAddress")]
    waap_address: Option<String>,
}

pub struct WalletCluster {
    pub canonical: WalletIdentity,
    pub wallets: Vec<WalletIdentity>,
}

pub fn chain_wallet_scoring_enabled() -> bool {
    std::env::var("CHAIN_WALLET_SCORING_ENABLED").as_deref() == Ok("true")
}

/// Read active members on every request so an unlink takes effect immediately.
pub async fn get_wallet_cluster(
    wallet: &WalletIdentity,
) -> Result<Option<WalletCluster>, Box<dyn std::error::Error + Send + Sync>> {
    use std::sync::OnceLock;
    use std::time::Duration;

    if !chain_wallet_scoring_enabled() {
        return Ok(None);
    }
    static CLIENT: OnceLock<reqwest::Client> = OnceLock::new();
    let client = if let Some(client) = CLIENT.get() {
        client
    } else {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(5))
            .redirect(reqwest::redirect::Policy::none())
            .build()?;
        CLIENT.get_or_init(|| client)
    };
    let origin = std::env::var("SILK_AUTH_SERVER_URL")?;
    let service_key = std::env::var("SILK_SERVICE_API_KEY")?;
    if origin.is_empty() || service_key.is_empty() {
        return Err("Silk linkage is not configured".into());
    }
    let url = format!(
        "{}/api/public/linked-wallets/by-identity/{}",
        origin.trim_end_matches('/'),
        wallet.address
    );
    let mut request = client.get(url).header("X-Service-Key", service_key);
    if let Some(chain_id) = wallet.chain_id {
        request = request.query(&[("chainId", chain_id)]);
    }
    let response = request.send().await?;
    if response.status() != reqwest::StatusCode::OK {
        return Err("Silk linkage request failed".into());
    }
    let SilkWalletCluster { mut wallets, waap_address } = response.json().await?;
    if wallets.iter().any(|member| {
        !crate::api::utils::is_valid_eth_address(&member.address)
            || member.address != member.address.to_lowercase()
            || member.chain_id.is_some_and(|id| !(1..=9_007_199_254_740_991).contains(&id))
    }) {
        return Err("Silk returned an invalid wallet identity".into());
    }
    let Some(address) = waap_address else { return Ok(None) };
    let canonical = WalletIdentity { address, chain_id: None };
    if !wallets.contains(wallet) || !wallets.contains(&canonical) {
        return Ok(None);
    }
    wallets.sort_by_key(WalletIdentity::key);
    wallets.dedup();
    Ok(Some(WalletCluster { canonical, wallets }))
}
