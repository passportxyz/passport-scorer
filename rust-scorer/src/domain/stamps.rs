use sqlx::{PgPool, Postgres, Transaction};
use tracing::info;

use crate::auth::credentials::validate_credentials_batch;
use crate::db::queries::stamps::{get_ceramic_cache_entries, get_latest_stamps_by_provider, delete_stamps, bulk_insert_stamps};
use crate::models::internal::ValidStamp;
use super::DomainError;

/// Add stamps for an address and optionally trigger rescoring
#[tracing::instrument(skip(pool))]
pub async fn add_stamps(
    address: &str,
    stamps: Vec<serde_json::Value>,
    passport_id: i64,
    pool: &PgPool,
) -> Result<Vec<ValidStamp>, DomainError> {
    let mut tx = pool.begin().await
        .map_err(|e| DomainError::Database(format!("Failed to start transaction: {}", e)))?;

    let result = add_stamps_internal(address, stamps, passport_id, &mut tx).await;

    match result {
        Ok(stamps) => {
            tx.commit().await
                .map_err(|e| DomainError::Database(format!("Failed to commit transaction: {}", e)))?;
            Ok(stamps)
        }
        Err(e) => {
            // Transaction will be rolled back automatically
            Err(e)
        }
    }
}

async fn add_stamps_internal(
    address: &str,
    stamps: Vec<serde_json::Value>,
    passport_id: i64,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<Vec<ValidStamp>, DomainError> {
    // Validate the stamps
    let validated_credentials = validate_credentials_batch(&stamps, address).await
        .map_err(|e| DomainError::Validation(e.to_string()))?;

    // Convert to internal ValidStamp format
    let valid_stamps: Vec<ValidStamp> = validated_credentials
        .into_iter()
        .map(|vc| ValidStamp {
            provider: vc.provider,
            credential: vc.credential,
            nullifiers: vc.nullifiers,
            expires_at: vc.expires_at,
        })
        .collect();

    if !valid_stamps.is_empty() {
        // Delete existing stamps first
        delete_stamps(tx, passport_id).await
            .map_err(|e| DomainError::Database(e.to_string()))?;

        // Insert the new stamps
        bulk_insert_stamps(tx, passport_id, &valid_stamps).await
            .map_err(|e| DomainError::Database(e.to_string()))?;

        info!("Added {} stamps for passport {}", valid_stamps.len(), passport_id);
    }

    Ok(valid_stamps)
}

/// Get all stamps for an address
#[tracing::instrument(skip(pool))]
pub async fn get_stamps(
    address: &str,
    pool: &PgPool,
) -> Result<Vec<serde_json::Value>, DomainError> {
    let ceramic_cache_entries = get_ceramic_cache_entries(pool, address).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    info!("Found {} stamps for address {}", ceramic_cache_entries.len(), address);

    Ok(ceramic_cache_entries.into_iter().map(|c| c.stamp).collect())
}

/// Get latest stamps per provider (deduplicated)
#[tracing::instrument(skip(pool))]
pub async fn get_latest_stamps(
    address: &str,
    pool: &PgPool,
) -> Result<Vec<serde_json::Value>, DomainError> {
    let latest_stamps = get_latest_stamps_by_provider(pool, address).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    info!("Found {} latest stamps for address {}", latest_stamps.len(), address);

    Ok(latest_stamps.into_iter().map(|c| c.stamp).collect())
}

/// Validate stamps and return validation results
#[tracing::instrument(skip_all)]
pub async fn validate_stamps(
    stamps: Vec<serde_json::Value>,
    address: &str,
) -> Result<Vec<ValidStamp>, DomainError> {
    let validated_credentials = validate_credentials_batch(&stamps, address).await
        .map_err(|e| DomainError::Validation(e.to_string()))?;

    // Convert to internal ValidStamp format
    let valid_stamps: Vec<ValidStamp> = validated_credentials
        .into_iter()
        .map(|vc| ValidStamp {
            provider: vc.provider,
            credential: vc.credential,
            nullifiers: vc.nullifiers,
            expires_at: vc.expires_at,
        })
        .collect();

    Ok(valid_stamps)
}