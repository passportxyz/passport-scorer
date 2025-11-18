use sqlx::PgPool;
use serde::{Deserialize, Serialize};
use super::DomainError;
use crate::db::queries::bans::{get_active_bans, Ban};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BanCheckResult {
    pub hash: Option<String>,
    pub is_banned: bool,
    pub ban_type: Option<String>,  // "account", "hash", or "single_stamp"
    pub end_time: Option<chrono::DateTime<chrono::Utc>>,
    pub reason: Option<String>,
}

/// Check a single credential against the fetched bans
fn check_bans_for<'a>(
    bans: &'a [Ban],
    address: &str,
    stamp_hash: &str,
    provider: &str,
) -> (bool, Option<String>, Option<&'a Ban>) {
    let parsed_address = address.to_lowercase();

    for ban in bans {
        let parsed_ban_address = ban.address.to_lowercase();

        // Check account-wide ban first
        if ban.ban_type == "account"
            && parsed_ban_address == parsed_address
            && ban.provider.is_empty()
        {
            return (true, Some("account".to_string()), Some(ban));
        }

        // Check hash ban
        if ban.ban_type == "hash" && ban.hash == stamp_hash {
            return (true, Some("hash".to_string()), Some(ban));
        }

        // Check address + provider ban (single_stamp)
        if ban.ban_type == "single_stamp"
            && parsed_ban_address == parsed_address
            && ban.provider == provider
        {
            return (true, Some("single_stamp".to_string()), Some(ban));
        }
    }

    (false, None, None)
}

/// Check credentials for bans
/// This is shared logic used by multiple endpoints (ceramic cache, internal check-bans, etc.)
#[tracing::instrument(skip(pool))]
pub async fn check_credentials_for_bans(
    address: &str,
    hashes: &[String],
    providers: &[String],
    pool: &PgPool,
) -> Result<Vec<BanCheckResult>, DomainError> {
    // Get all active bans for this address and hashes
    let bans = get_active_bans(pool, address, hashes)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // Check each credential (by provider) against the bans
    // Note: hashes and providers are parallel arrays
    let results: Vec<BanCheckResult> = hashes
        .iter()
        .zip(providers.iter())
        .map(|(hash, provider)| {
            let (is_banned, ban_type, ban) = check_bans_for(&bans, address, hash, provider);
            BanCheckResult {
                hash: Some(hash.clone()),
                is_banned,
                ban_type,
                end_time: ban.and_then(|b| b.end_time),
                reason: ban.and_then(|b| b.reason.clone()),
            }
        })
        .collect();

    Ok(results)
}

/// Check if an address is banned (account-wide ban)
#[tracing::instrument(skip(pool))]
pub async fn is_address_banned(
    address: &str,
    pool: &PgPool,
) -> Result<bool, DomainError> {
    let bans = get_active_bans(pool, address, &[])
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // Check for account-wide ban
    let parsed_address = address.to_lowercase();
    for ban in &bans {
        if ban.ban_type == "account"
            && ban.address.to_lowercase() == parsed_address
            && ban.provider.is_empty()
        {
            return Ok(true);
        }
    }

    Ok(false)
}