use sqlx::PgPool;
use crate::db::errors::DatabaseError;
use crate::models::django::DjangoCeramicCache;

/// Get all ceramic cache entries for an address
pub async fn get_ceramic_cache_entries(
    _pool: &PgPool,
    _address: &str,
) -> Result<Vec<DjangoCeramicCache>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(vec![])
}

/// Get latest stamps per provider (deduplicated by updated_at)
pub async fn get_latest_stamps_by_provider(
    _pool: &PgPool,
    _address: &str,
) -> Result<Vec<DjangoCeramicCache>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(vec![])
}
