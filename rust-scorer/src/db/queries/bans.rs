use sqlx::PgPool;
use std::collections::HashSet;
use crate::db::errors::DatabaseError;

/// Check ADDRESS type bans
pub async fn check_address_bans(
    _pool: &PgPool,
    _addresses: &[String],
) -> Result<HashSet<String>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(HashSet::new())
}

/// Check HASH type bans
pub async fn check_hash_bans(
    _pool: &PgPool,
    _hashes: &[String],
) -> Result<HashSet<String>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(HashSet::new())
}

/// Check PROVIDER type bans
pub async fn check_provider_bans(
    _pool: &PgPool,
    _provider: &str,
) -> Result<bool, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(false)
}
