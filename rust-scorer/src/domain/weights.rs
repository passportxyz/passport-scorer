use rust_decimal::Decimal;
use sqlx::PgPool;
use std::collections::HashMap;
use tracing::info;

use crate::db::read_ops::load_scorer_config;
use super::DomainError;

/// Get scorer weights for a given scorer_id
/// Returns either community-specific weights or default weights
#[tracing::instrument(skip(pool))]
pub async fn get_scorer_weights(
    scorer_id: Option<i64>,
    pool: &PgPool,
) -> Result<HashMap<String, f64>, DomainError> {
    match scorer_id {
        Some(id) => {
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
        None => {
            info!("Returning default weights");
            Ok(get_default_weights())
        }
    }
}

/// Get default weights when no scorer_id is provided
pub fn get_default_weights() -> HashMap<String, f64> {
    // These should match the default weights from Python
    // TODO: Load these from configuration or constants
    let mut weights = HashMap::new();

    // Example default weights - these should be updated to match Python defaults
    weights.insert("Ens".to_string(), 1.0);
    weights.insert("NFT".to_string(), 1.0);
    weights.insert("Google".to_string(), 1.0);
    weights.insert("Twitter".to_string(), 1.0);
    weights.insert("Discord".to_string(), 1.0);
    weights.insert("Github".to_string(), 1.0);
    weights.insert("Linkedin".to_string(), 1.0);
    weights.insert("Facebook".to_string(), 1.0);
    weights.insert("Brightid".to_string(), 1.0);
    weights.insert("Poh".to_string(), 1.0);

    weights
}