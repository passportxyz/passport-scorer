use sqlx::PgPool;
use rust_decimal::Decimal;
use std::str::FromStr;
use crate::db::errors::DatabaseError;

#[derive(Debug, Clone)]
pub struct ScorerWeights {
    pub weights: serde_json::Value,
    pub threshold: Decimal,
}

/// Get scorer weights from BinaryWeightedScorer or WeightedScorer tables
pub async fn get_scorer_weights(
    pool: &PgPool,
    scorer_id: i64,
) -> Result<Option<ScorerWeights>, DatabaseError> {
    // Try BinaryWeightedScorer first
    let result = sqlx::query!(
        r#"
        SELECT weights, threshold
        FROM scorer_weighted_binaryweightedscorer
        WHERE scorer_ptr_id = $1
        "#,
        scorer_id
    )
    .fetch_optional(pool)
    .await?;

    if let Some(row) = result {
        // Skip if weights is null
        if let Some(weights) = row.weights {
            return Ok(Some(ScorerWeights {
                weights,
                threshold: row.threshold,
            }));
        }
    }

    // Fallback to WeightedScorer
    let result = sqlx::query!(
        r#"
        SELECT weights, threshold
        FROM scorer_weighted_weightedscorer
        WHERE scorer_ptr_id = $1
        "#,
        scorer_id
    )
    .fetch_optional(pool)
    .await?;

    Ok(result.and_then(|row| {
        row.weights.map(|weights| ScorerWeights {
            weights,
            threshold: row.threshold.unwrap_or_else(|| Decimal::from_str_exact("2.5").unwrap()),
        })
    }))
}

/// Get default scorer weights
pub fn get_default_scorer_weights() -> ScorerWeights {
    // TODO: Load from configuration
    ScorerWeights {
        weights: serde_json::json!({
            "Ens": 1.0,
            "NFT": 1.0,
            "Google": 1.0,
            "Twitter": 1.0,
            "Discord": 1.0,
            "Github": 1.0,
            "Linkedin": 1.0,
            "Facebook": 1.0,
            "Brightid": 1.0,
            "Poh": 1.0,
        }),
        threshold: Decimal::from(20),
    }
}
