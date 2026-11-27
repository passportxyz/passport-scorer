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

#[derive(serde::Deserialize)]
struct WalletIdentity {
    address: String,
    #[serde(rename = "chainId")]
    chain_id: Option<i64>,
}

#[derive(serde::Deserialize)]
struct WalletCluster {
    wallets: Vec<WalletIdentity>,
}

/// Ask Silk for the exact identity. Scoped scoring never falls back to a
/// legacy address-only call or a cached link when Silk is unavailable.
pub async fn is_linked_contract_wallet(
    chain_id: i64,
    address: &str,
) -> Result<bool, Box<dyn std::error::Error + Send + Sync>> {
    use std::sync::OnceLock;
    use std::time::Duration;

    if std::env::var("CHAIN_WALLET_SCORING_ENABLED").as_deref() != Ok("true") {
        return Err("Chain wallet scoring is disabled".into());
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
    let url = format!("{}/api/public/linked-wallets/by-identity/{address}", origin.trim_end_matches('/'));
    let response = client
        .get(url)
        .query(&[("chainId", chain_id)])
        .header("X-Service-Key", service_key)
        .send()
        .await?;
    if response.status() != reqwest::StatusCode::OK {
        return Err("Silk linkage request failed".into());
    }
    let cluster: WalletCluster = response.json().await?;
    Ok(cluster.wallets.iter().any(|member| member.chain_id == Some(chain_id) && member.address == address))
}
