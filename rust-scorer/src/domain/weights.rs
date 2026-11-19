use rust_decimal::Decimal;
use sqlx::PgPool;
use std::collections::HashMap;
use tracing::info;

use crate::db::queries::load_scorer_config;
use super::DomainError;

/// Get scorer weights for a given scorer_id
/// Returns either community-specific weights or default weights
#[tracing::instrument(skip(pool))]
pub async fn get_scorer_weights(
    scorer_id: Option<i64>,
    pool: &PgPool,
) -> Result<HashMap<String, f64>, DomainError> {
    // If scorer_id is not provided, use CERAMIC_CACHE_SCORER_ID from environment
    let id = match scorer_id {
        Some(id) => id,
        None => {
            let env_scorer_id = std::env::var("CERAMIC_CACHE_SCORER_ID")
                .map_err(|_| DomainError::Internal("CERAMIC_CACHE_SCORER_ID not set".to_string()))?;
            env_scorer_id.parse::<i64>()
                .map_err(|e| DomainError::Internal(format!("Invalid CERAMIC_CACHE_SCORER_ID: {}", e)))?
        }
    };

    info!("Loading weights for scorer_id: {}", id);
    let scorer_config = load_scorer_config(pool, id).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // Parse weights from JSON to HashMap<String, Decimal>
    let decimal_weights: HashMap<String, Decimal> = serde_json::from_value(scorer_config.weights)
        .map_err(|e| DomainError::Internal(format!("Failed to parse weights: {}", e)))?;

    // Convert Decimal to f64 for API response
    let weights: HashMap<String, f64> = decimal_weights
        .into_iter()
        .map(|(k, v)| (k, v.to_string().parse::<f64>().unwrap_or(0.0)))
        .collect();

    Ok(weights)
}

