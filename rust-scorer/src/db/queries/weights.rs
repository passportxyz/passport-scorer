use sqlx::PgPool;
use rust_decimal::Decimal;
use tracing::{info, debug};

use crate::db::errors::DatabaseError;
use crate::models::django::DjangoBinaryWeightedScorer;

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
            threshold: row.threshold,
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

/// Load binary weighted scorer configuration
#[tracing::instrument(skip(pool), fields(scorer_id = scorer_id))]
pub async fn load_scorer_config(
    pool: &PgPool,
    scorer_id: i64,
) -> Result<DjangoBinaryWeightedScorer, DatabaseError> {
    debug!("Loading scorer config for scorer_id: {}", scorer_id);

    // Try BinaryWeightedScorer first, then fall back to WeightedScorer
    let scorer = match sqlx::query_as::<_, DjangoBinaryWeightedScorer>(
        r#"
        SELECT
            scorer_ptr_id,
            weights,
            threshold
        FROM scorer_weighted_binaryweightedscorer
        WHERE scorer_ptr_id = $1
        "#
    )
    .bind(scorer_id)
    .fetch_one(pool)
    .await
    {
        Ok(scorer) => scorer,
        Err(sqlx::Error::RowNotFound) => {
            // Try WeightedScorer table as fallback
            sqlx::query_as::<_, DjangoBinaryWeightedScorer>(
                r#"
                SELECT
                    scorer_ptr_id,
                    weights,
                    threshold
                FROM scorer_weighted_weightedscorer
                WHERE scorer_ptr_id = $1
                "#
            )
            .bind(scorer_id)
            .fetch_one(pool)
            .await
            .map_err(|e| match e {
                sqlx::Error::RowNotFound => DatabaseError::NotFound(
                    format!("Scorer configuration not found for scorer_id: {}", scorer_id)
                ),
                _ => DatabaseError::QueryError(e),
            })?
        }
        Err(e) => return Err(DatabaseError::QueryError(e)),
    };

    info!("Loaded scorer config with threshold: {}", scorer.threshold);
    Ok(scorer)
}
