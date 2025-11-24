use serde_json::Value as JsonValue;
use sqlx::{PgPool, Transaction, Postgres};
use tracing::{info, debug};

use crate::db::errors::DatabaseError;
use crate::models::django::DjangoCeramicCache;
use crate::models::internal::ValidStamp;

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
            type AS "stamp_type: _",
            deleted_at,
            created_at,
            updated_at
        FROM ceramic_cache_ceramiccache
        WHERE address = $1
        AND deleted_at IS NULL
        AND type = 1
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
        AND type = 1
        ORDER BY provider, updated_at DESC
        "#,
        address
    )
    .fetch_all(pool)
    .await?;

    Ok(entries)
}

/// Delete all existing stamps for a passport
#[tracing::instrument(skip(tx), fields(passport_id = passport_id))]
pub async fn delete_stamps(
    tx: &mut Transaction<'_, Postgres>,
    passport_id: i64,
) -> Result<u64, DatabaseError> {
    debug!("Deleting existing stamps for passport_id: {}", passport_id);

    let result = sqlx::query(
        "DELETE FROM registry_stamp WHERE passport_id = $1"
    )
    .bind(passport_id)
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;

    let deleted = result.rows_affected();
    info!("Deleted {} existing stamps", deleted);
    Ok(deleted)
}

/// Bulk insert stamps
#[tracing::instrument(skip(tx, stamps), fields(passport_id = passport_id))]
pub async fn bulk_insert_stamps(
    tx: &mut Transaction<'_, Postgres>,
    passport_id: i64,
    stamps: &[ValidStamp],
) -> Result<u64, DatabaseError> {
    if stamps.is_empty() {
        info!("No stamps to insert");
        return Ok(0);
    }

    debug!("Bulk inserting {} stamps for passport_id: {}", stamps.len(), passport_id);

    let providers: Vec<String> = stamps.iter().map(|s| s.provider.clone()).collect();
    let credentials: Vec<JsonValue> = stamps.iter().map(|s| s.credential.clone()).collect();
    let passport_ids: Vec<i64> = vec![passport_id; stamps.len()];

    let result = sqlx::query(
        r#"
        INSERT INTO registry_stamp (passport_id, provider, credential)
        SELECT * FROM UNNEST($1::bigint[], $2::text[], $3::jsonb[])
        AS t(passport_id, provider, credential)
        "#
    )
    .bind(&passport_ids[..])
    .bind(&providers[..])
    .bind(&credentials[..])
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;

    let inserted = result.rows_affected();
    info!("Inserted {} stamps", inserted);
    Ok(inserted)
}