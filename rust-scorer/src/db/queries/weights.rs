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

/// Load the scorer configuration of a community.
///
/// Takes the community id, which every caller passes (the `scorer_id` in the
/// API paths is a community id), and follows `account_community.scorer_id` to
/// the scorer row, as Python's `Community.get_scorer` does. The two ids differ
/// once a community changes scorer type: `update_community_scorers` creates a
/// new scorer row and points the community at it.
#[tracing::instrument(skip(pool), fields(community_id = community_id))]
pub async fn load_scorer_config(
    pool: &PgPool,
    community_id: i64,
) -> Result<DjangoBinaryWeightedScorer, DatabaseError> {
    debug!("Loading scorer config for community_id: {}", community_id);

    // Try BinaryWeightedScorer first, then fall back to WeightedScorer
    let scorer = match sqlx::query_as::<_, DjangoBinaryWeightedScorer>(
        r#"
        SELECT
            s.scorer_ptr_id,
            s.weights,
            s.threshold
        FROM scorer_weighted_binaryweightedscorer s
        JOIN account_community c ON c.scorer_id = s.scorer_ptr_id
        WHERE c.id = $1
        "#
    )
    .bind(community_id)
    .fetch_one(pool)
    .await
    {
        Ok(scorer) => scorer,
        Err(sqlx::Error::RowNotFound) => {
            // Try WeightedScorer table as fallback
            sqlx::query_as::<_, DjangoBinaryWeightedScorer>(
                r#"
                SELECT
                    s.scorer_ptr_id,
                    s.weights,
                    s.threshold
                FROM scorer_weighted_weightedscorer s
                JOIN account_community c ON c.scorer_id = s.scorer_ptr_id
                WHERE c.id = $1
                "#
            )
            .bind(community_id)
            .fetch_one(pool)
            .await
            .map_err(|e| match e {
                sqlx::Error::RowNotFound => DatabaseError::NotFound(
                    format!("Scorer configuration not found for community_id: {}", community_id)
                ),
                _ => DatabaseError::QueryError(e),
            })?
        }
        Err(e) => return Err(DatabaseError::QueryError(e)),
    };

    info!("Loaded scorer config with threshold: {}", scorer.threshold);
    Ok(scorer)
}
