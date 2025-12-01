use sqlx::PgPool;
use chrono::{DateTime, Utc};
use crate::db::errors::DatabaseError;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct Ban {
    pub id: i64,
    #[sqlx(rename = "type")]
    pub ban_type: String,
    pub provider: String,
    pub hash: String,
    pub address: String,
    pub end_time: Option<DateTime<Utc>>,
    pub reason: Option<String>,
}

/// Get active bans for address and hashes
pub async fn get_active_bans(
    pool: &PgPool,
    address: &str,
    hashes: &[String],
) -> Result<Vec<Ban>, DatabaseError> {
    let bans = sqlx::query_as!(
        Ban,
        r#"
        SELECT
            id,
            type as ban_type,
            provider,
            hash,
            address,
            end_time,
            reason
        FROM ceramic_cache_ban
        WHERE (address = $1 OR hash = ANY($2))
        AND (end_time IS NULL OR end_time > NOW())
        "#,
        address,
        hashes
    )
    .fetch_all(pool)
    .await?;

    Ok(bans)
}

/// Check if proof values are revoked - returns the revoked proof values
pub async fn check_revocations(
    pool: &PgPool,
    proof_values: &[String],
) -> Result<Vec<String>, DatabaseError> {
    let revoked = sqlx::query_scalar!(
        r#"
        SELECT proof_value
        FROM ceramic_cache_revocation
        WHERE proof_value = ANY($1)
        "#,
        proof_values
    )
    .fetch_all(pool)
    .await?;

    Ok(revoked)
}