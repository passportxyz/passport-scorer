use sqlx::PgPool;
use crate::db::errors::DatabaseError;

#[derive(Debug, Clone)]
pub struct Ban {
    pub id: i64,
    pub ban_type: String,
    pub provider: Option<String>,
    pub hash: Option<String>,
    pub address: Option<String>,
    pub end_time: Option<chrono::DateTime<chrono::Utc>>,
    pub reason: Option<String>,
    pub ban_list_id: Option<i64>,
}

/// Get active bans for address and hashes
pub async fn get_active_bans(
    pool: &PgPool,
    address: &str,
    hashes: &[String],
) -> Result<Vec<Ban>, DatabaseError> {
    // TODO: Implement ban query
    // Query ceramic_cache_ban table
    // WHERE (address = $1 OR hash = ANY($2))
    // AND (end_time IS NULL OR end_time > NOW())
    Ok(vec![])
}

/// Check if proof values are revoked
pub async fn check_revocations(
    pool: &PgPool,
    proof_values: &[String],
) -> Result<Vec<String>, DatabaseError> {
    // TODO: Implement revocation check
    // Query ceramic_cache_revocation table
    // WHERE proof_value = ANY($1)
    Ok(vec![])
}