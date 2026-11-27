//! Score the chain identity using the shared nullifier rules and a separate
//! score row. It never creates a legacy Passport, event or human-points row.

use rust_decimal::Decimal;
use serde::Serialize;
use sqlx::PgPool;
use std::collections::HashMap;

use crate::auth::credentials::validate_chain_credentials;
use crate::db::{DatabaseError, queries};
use crate::domain::dedup::lifo_dedup_for_chain;
use crate::domain::scoring::{ScorerConfig, build_scoring_result};
use crate::models::{internal::ValidStamp, v2_api::V2ScoreResponse};

#[derive(Serialize)]
pub struct ChainWalletScoreResponse {
    pub chain_id: i64,
    #[serde(flatten)]
    pub score: V2ScoreResponse,
}

pub async fn score_chain_wallet(
    pool: &PgPool,
    community_id: i64,
    chain_id: i64,
    address: &str,
) -> Result<ChainWalletScoreResponse, DatabaseError> {
    let credentials = queries::stamps::get_latest_stamps_for_chain(pool, address, chain_id).await?;
    let stamps: Vec<_> = validate_chain_credentials(&credentials, address, chain_id)
        .await?
        .into_iter()
        .map(|credential| ValidStamp {
            provider: credential.provider,
            credential: credential.credential,
            nullifiers: credential.nullifiers,
            expires_at: credential.expires_at,
        })
        .collect();
    let config = queries::load_scorer_config(pool, community_id).await?;
    let mut weights: HashMap<String, Decimal> = serde_json::from_value(config.weights)?;
    weights.extend(queries::weights::get_chain_wallet_custom_weights(pool, community_id).await?);
    let mut tx = pool.begin().await?;
    let deduped =
        lifo_dedup_for_chain(&stamps, address, chain_id, community_id, &weights, &mut tx).await?;
    let score = build_scoring_result(
        address,
        community_id,
        deduped,
        ScorerConfig {
            weights,
            threshold: config.threshold,
        },
    )?;
    let response = ChainWalletScoreResponse {
        chain_id,
        score: score.to_v2_response(),
    };
    save_chain_wallet_score(&mut tx, community_id, address, &response).await?;
    tx.commit().await?;
    Ok(response)
}

async fn save_chain_wallet_score(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    community_id: i64,
    address: &str,
    response: &ChainWalletScoreResponse,
) -> Result<(), DatabaseError> {
    let payload = serde_json::to_value(response)?;
    sqlx::query(
        "INSERT INTO registry_chainwalletscore (community_id, chain_id, address, response)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT (community_id, chain_id, address)
         DO UPDATE SET response = EXCLUDED.response",
    )
    .bind(community_id)
    .bind(response.chain_id)
    .bind(address.to_lowercase())
    .bind(payload)
    .execute(&mut **tx)
    .await?;
    Ok(())
}
