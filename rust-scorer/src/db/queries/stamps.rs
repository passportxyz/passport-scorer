use sqlx::PgPool;
use crate::db::errors::DatabaseError;
use crate::models::django::DjangoCeramicCache;

/// Get all ceramic cache entries for an address
pub async fn get_ceramic_cache_entries(
    pool: &PgPool,
    address: &str,
) -> Result<Vec<DjangoCeramicCache>, DatabaseError> {
    let entries = sqlx::query_as!(
        DjangoCeramicCache,
        r#"
        SELECT
            id,
            address,
            provider,
            stamp,
            type AS stamp_type,
            deleted_at,
            created_at,
            updated_at
        FROM ceramic_cache_ceramiccache
        WHERE address = $1
        AND deleted_at IS NULL
        AND type = 'V1'
        ORDER BY provider, updated_at DESC
        "#,
        address
    )
    .fetch_all(pool)
    .await?;

    Ok(entries)
}

/// Get latest stamps per provider (deduplicated by updated_at)
pub async fn get_latest_stamps_by_provider(
    pool: &PgPool,
    address: &str,
) -> Result<Vec<DjangoCeramicCache>, DatabaseError> {
    let entries = sqlx::query_as!(
        DjangoCeramicCache,
        r#"
        SELECT DISTINCT ON (provider)
            id,
            address,
            provider,
            stamp,
            type AS "stamp_type: _",
            deleted_at,
            created_at,
            updated_at
        FROM ceramic_cache_ceramiccache
        WHERE address = $1
        AND deleted_at IS NULL
        AND type = 'V1'
        ORDER BY provider, updated_at DESC
        "#,
        address
    )
    .fetch_all(pool)
    .await?;

    Ok(entries)
}