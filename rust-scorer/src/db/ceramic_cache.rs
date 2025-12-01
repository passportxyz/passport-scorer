use chrono::{DateTime, Utc};
use serde_json::Value;
use sqlx::{PgPool, Postgres, Row, Transaction};
use tracing::{debug, info};

use crate::db::errors::{DatabaseError, Result};
use crate::models::v2_api::CachedStampResponse;

/// Extract provider list from stamps array
/// Filters out any stamps that don't have the required provider field
pub fn extract_providers(stamps: &[Value]) -> Vec<String> {
    stamps
        .iter()
        .filter_map(|stamp| {
            stamp
                .get("credentialSubject")
                .and_then(|cs| cs.get("provider"))
                .and_then(|p| p.as_str())
                .map(|s| s.to_string())
        })
        .collect()
}

/// Soft delete stamps by provider for a given address
/// Sets deleted_at and updated_at to NOW() for matching stamps
#[tracing::instrument(
    skip(tx),
    fields(address = %address, provider_count = providers.len())
)]
pub async fn soft_delete_stamps_by_provider(
    address: &str,
    providers: &[String],
    tx: &mut Transaction<'_, Postgres>,
) -> Result<u64> {
    debug!("Soft deleting stamps for {} providers", providers.len());

    if providers.is_empty() {
        return Ok(0);
    }

    let result = sqlx::query(
        r#"
        UPDATE ceramic_cache_ceramiccache
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE address = $1
          AND provider = ANY($2)
          AND type = 1
          AND deleted_at IS NULL
        "#,
    )
    .bind(address)
    .bind(providers)
    .execute(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;

    let rows_affected = result.rows_affected();
    info!("Soft deleted {} stamps", rows_affected);
    Ok(rows_affected)
}

/// Bulk insert ceramic cache stamps
/// All stamps are inserted with type=V1 (1), compose_db_save_status='pending'
#[tracing::instrument(
    skip(tx, stamps),
    fields(
        address = %address,
        stamp_count = stamps.len(),
        source_app = source_app,
        source_scorer_id = ?source_scorer_id
    )
)]
pub async fn bulk_insert_ceramic_cache_stamps(
    address: &str,
    stamps: &[Value],
    source_app: i32,
    source_scorer_id: Option<i64>,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<()> {
    debug!("Bulk inserting {} stamps", stamps.len());

    if stamps.is_empty() {
        return Ok(());
    }

    // Prepare arrays for bulk insert
    let mut providers = Vec::new();
    let mut stamp_jsons = Vec::new();
    let mut proof_values = Vec::new();
    let mut issuance_dates: Vec<Option<DateTime<Utc>>> = Vec::new();
    let mut expiration_dates: Vec<Option<DateTime<Utc>>> = Vec::new();

    for stamp in stamps {
        // Extract required fields
        let provider = stamp
            .get("credentialSubject")
            .and_then(|cs| cs.get("provider"))
            .and_then(|p| p.as_str())
            .ok_or_else(|| DatabaseError::InvalidData("Missing provider in stamp".into()))?;

        let proof_value = stamp
            .get("proof")
            .and_then(|p| p.get("proofValue"))
            .and_then(|pv| pv.as_str())
            .ok_or_else(|| DatabaseError::InvalidData("Missing proof.proofValue in stamp".into()))?;

        // Extract optional date fields
        let issuance_date = stamp
            .get("issuanceDate")
            .and_then(|d| d.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| dt.with_timezone(&Utc));

        let expiration_date = stamp
            .get("expirationDate")
            .and_then(|d| d.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| dt.with_timezone(&Utc));

        providers.push(provider.to_string());
        stamp_jsons.push(stamp.clone());
        proof_values.push(proof_value.to_string());
        issuance_dates.push(issuance_date);
        expiration_dates.push(expiration_date);
    }

    // PostgreSQL UNNEST-based bulk insert
    // This is much more efficient than individual inserts
    sqlx::query(
        r#"
        INSERT INTO ceramic_cache_ceramiccache (
            type,
            address,
            provider,
            stamp,
            proof_value,
            updated_at,
            compose_db_save_status,
            compose_db_stream_id,
            issuance_date,
            expiration_date,
            source_app,
            source_scorer_id
        )
        SELECT
            1,                  -- type (V1)
            LOWER($1),          -- address
            p.provider,
            p.stamp,
            p.proof_value,
            NOW(),              -- updated_at
            'pending',          -- compose_db_save_status
            '',                 -- compose_db_stream_id
            p.issuance_date,
            p.expiration_date,
            $2,                 -- source_app
            $3                  -- source_scorer_id
        FROM UNNEST(
            $4::varchar[],
            $5::jsonb[],
            $6::varchar[],
            $7::timestamptz[],
            $8::timestamptz[]
        ) AS p(provider, stamp, proof_value, issuance_date, expiration_date)
        ON CONFLICT (type, address, provider) WHERE deleted_at IS NULL
        DO NOTHING
        "#,
    )
    .bind(address)
    .bind(source_app)
    .bind(source_scorer_id)
    .bind(&providers)
    .bind(&stamp_jsons)
    .bind(&proof_values)
    .bind(&issuance_dates)
    .bind(&expiration_dates)
    .execute(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;

    info!("Bulk inserted {} stamps", stamps.len());
    Ok(())
}

/// Get stamps from cache for an address
/// Filters for V1 type, non-deleted, and non-revoked stamps
/// Revocation is checked via LEFT JOIN with ceramic_cache_revocation table
#[tracing::instrument(skip(pool), fields(address = %address))]
pub async fn get_stamps_from_cache(
    pool: &PgPool,
    address: &str,
) -> Result<Vec<CachedStampResponse>> {
    debug!("Getting stamps from cache for address: {}", address);

    let rows = sqlx::query(
        r#"
        SELECT
            c.id,
            c.address,
            c.provider,
            c.stamp
        FROM ceramic_cache_ceramiccache c
        LEFT JOIN ceramic_cache_revocation r
            ON c.id = r.ceramic_cache_id
        WHERE c.address = $1
          AND c.type = 1
          AND c.deleted_at IS NULL
          AND r.id IS NULL
        ORDER BY c.created_at DESC
        "#,
    )
    .bind(address)
    .fetch_all(pool)
    .await
    .map_err(DatabaseError::QueryError)?;

    let stamps: Vec<CachedStampResponse> = rows
        .iter()
        .map(|row| CachedStampResponse {
            id: row.get("id"),
            address: row.get("address"),
            provider: row.get("provider"),
            stamp: row.get("stamp"),
        })
        .collect();

    info!("Found {} stamps in cache for address {}", stamps.len(), address);
    Ok(stamps)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_extract_providers() {
        let stamps = vec![
            json!({
                "credentialSubject": {
                    "provider": "Github"
                }
            }),
            json!({
                "credentialSubject": {
                    "provider": "Twitter"
                }
            }),
            json!({
                "invalid": "stamp"  // Missing provider
            }),
        ];

        let providers = extract_providers(&stamps);
        assert_eq!(providers, vec!["Github", "Twitter"]);
    }

    #[test]
    fn test_extract_providers_empty() {
        let stamps: Vec<Value> = vec![];
        let providers = extract_providers(&stamps);
        assert_eq!(providers.len(), 0);
    }

    #[test]
    fn test_extract_providers_all_invalid() {
        let stamps = vec![
            json!({"invalid": "stamp"}),
            json!({"credentialSubject": {}}),
        ];
        let providers = extract_providers(&stamps);
        assert_eq!(providers.len(), 0);
    }
}
