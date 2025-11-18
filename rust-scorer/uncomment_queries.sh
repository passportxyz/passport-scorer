#!/bin/bash

echo "Uncommenting SQLX queries..."

# Fix scoring.rs
cat > src/db/queries/scoring.rs << 'EOF'
use sqlx::{PgPool, Postgres, Transaction};
use crate::db::errors::DatabaseError;

/// Get passport by address and scorer_id
pub async fn get_passport(
    pool: &PgPool,
    address: &str,
    scorer_id: i64,
) -> Result<Option<i64>, DatabaseError> {
    let result = sqlx::query!(
        r#"
        SELECT id FROM registry_passport
        WHERE address = $1 AND community_id = $2
        "#,
        address,
        scorer_id
    )
    .fetch_optional(pool)
    .await?;

    Ok(result.map(|r| r.id))
}

/// Upsert passport record and return ID
pub async fn upsert_passport_record(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    scorer_id: i64,
) -> Result<i64, DatabaseError> {
    let result = sqlx::query!(
        r#"
        INSERT INTO registry_passport (address, community_id)
        VALUES ($1, $2)
        ON CONFLICT (address, community_id)
        DO UPDATE SET address = EXCLUDED.address
        RETURNING id
        "#,
        address,
        scorer_id
    )
    .fetch_one(&mut **tx)
    .await?;

    Ok(result.id)
}

/// Get score by passport_id
pub async fn get_score(
    pool: &PgPool,
    passport_id: i64,
) -> Result<Option<i64>, DatabaseError> {
    let result = sqlx::query!(
        r#"
        SELECT id FROM registry_score
        WHERE passport_id = $1
        "#,
        passport_id
    )
    .fetch_optional(pool)
    .await?;

    Ok(result.map(|r| r.id))
}

/// Upsert score record
pub async fn upsert_score_record(
    tx: &mut Transaction<'_, Postgres>,
    passport_id: i64,
    score: rust_decimal::Decimal,
    _threshold: rust_decimal::Decimal,
    stamps: serde_json::Value,
    stamp_scores: serde_json::Value,
    evidence: serde_json::Value,
    expiration_date: Option<chrono::DateTime<chrono::Utc>>,
) -> Result<i64, DatabaseError> {
    let result = sqlx::query!(
        r#"
        INSERT INTO registry_score (
            passport_id, score, last_score_timestamp, status,
            evidence, stamp_scores, stamps, expiration_date, error
        )
        VALUES ($1, $2, NOW(), 'DONE', $3, $4, $5, $6, NULL)
        ON CONFLICT (passport_id)
        DO UPDATE SET
            score = EXCLUDED.score,
            last_score_timestamp = EXCLUDED.last_score_timestamp,
            status = EXCLUDED.status,
            evidence = EXCLUDED.evidence,
            stamp_scores = EXCLUDED.stamp_scores,
            stamps = EXCLUDED.stamps,
            expiration_date = EXCLUDED.expiration_date,
            error = EXCLUDED.error
        RETURNING id
        "#,
        passport_id,
        score,
        evidence,
        stamp_scores,
        stamps,
        expiration_date
    )
    .fetch_one(&mut **tx)
    .await?;

    Ok(result.id)
}
EOF

# Fix weights.rs
cat > src/db/queries/weights.rs << 'EOF'
use sqlx::PgPool;
use rust_decimal::Decimal;
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
        return Ok(Some(ScorerWeights {
            weights: row.weights,
            threshold: row.threshold,
        }));
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

    Ok(result.map(|row| ScorerWeights {
        weights: row.weights,
        threshold: row.threshold,
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
EOF

echo "Queries uncommented in scoring.rs and weights.rs"
echo "utils.rs already has working queries"
echo "Now run: cargo sqlx prepare"