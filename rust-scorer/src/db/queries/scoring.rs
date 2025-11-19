use sqlx::{PgPool, Postgres, Transaction};
use tracing::{info, debug};

use crate::db::errors::DatabaseError;
use crate::models::django::{DjangoCommunity, DjangoScoreFields};

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

/// Load community settings
#[tracing::instrument(skip(pool), fields(community_id = community_id))]
pub async fn load_community(
    pool: &PgPool,
    community_id: i64,
) -> Result<DjangoCommunity, DatabaseError> {
    debug!("Loading community settings for community_id: {}", community_id);

    let community = sqlx::query_as::<_, DjangoCommunity>(
        r#"
        SELECT
            id,
            name,
            description,
            human_points_program,
            created_at
        FROM account_community
        WHERE id = $1
        "#
    )
    .bind(community_id)
    .fetch_one(pool)
    .await
    .map_err(|e| match e {
        sqlx::Error::RowNotFound => DatabaseError::NotFound(
            format!("Community not found for id: {}", community_id)
        ),
        _ => DatabaseError::QueryError(e),
    })?;

    info!("Loaded community '{}' with human_points_program: {}",
        community.name, community.human_points_program);
    Ok(community)
}

/// Upsert a score record using DjangoScoreFields
#[tracing::instrument(skip(tx, score_fields), fields(passport_id = passport_id))]
pub async fn upsert_score(
    tx: &mut Transaction<'_, Postgres>,
    passport_id: i64,
    score_fields: &DjangoScoreFields,
) -> Result<i64, DatabaseError> {
    debug!("Upserting score for passport_id: {}", passport_id);

    let result = sqlx::query!(
        r#"
        INSERT INTO registry_score (
            passport_id,
            score,
            status,
            last_score_timestamp,
            evidence,
            stamps,
            stamp_scores,
            expiration_date,
            error
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (passport_id)
        DO UPDATE SET
            score = EXCLUDED.score,
            status = EXCLUDED.status,
            last_score_timestamp = EXCLUDED.last_score_timestamp,
            evidence = EXCLUDED.evidence,
            stamps = EXCLUDED.stamps,
            stamp_scores = EXCLUDED.stamp_scores,
            expiration_date = EXCLUDED.expiration_date,
            error = EXCLUDED.error
        RETURNING id
        "#,
        passport_id,
        score_fields.score,
        score_fields.status,
        score_fields.last_score_timestamp,
        score_fields.evidence,
        serde_json::to_value(&score_fields.stamps).unwrap(),
        score_fields.stamp_scores,
        score_fields.expiration_date,
        score_fields.error
    )
    .fetch_one(&mut **tx)
    .await?;

    info!("Upserted score with ID: {} (score: {})", result.id, score_fields.score);
    Ok(result.id)
}
