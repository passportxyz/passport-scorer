// External API handlers - require API key authentication
// These are thin handlers that orchestrate HTTP concerns and call domain logic

use axum::{
    extract::{Path, State},
    http::HeaderMap,
    Json,
};
use sqlx::PgPool;
use tracing::info;

use crate::api::error::{ApiError, ApiResult};
use crate::api::utils::is_valid_eth_address;
use crate::auth::api_key::ApiKeyValidator;
use crate::domain;
use crate::models::v2_api::V2ScoreResponse;

/// External score handler - requires API key authentication
#[tracing::instrument(
    skip(pool, headers),
    fields(
        scorer_id = scorer_id,
        address = %address
    )
)]
pub async fn score_address_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<Json<V2ScoreResponse>> {
    info!("Processing external score request");

    // 1. Input validation
    let address = address.to_lowercase();
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest("Invalid Ethereum address format".to_string()));
    }

    // 2. Authentication - validate API key and check permissions
    let x_api_key = headers.get("X-API-Key")
        .and_then(|h| h.to_str().ok());
    let auth_header = headers.get("Authorization")
        .and_then(|h| h.to_str().ok());

    let request_path = format!("/v2/stamps/{}/score/{}", scorer_id, address);

    let api_key_data = ApiKeyValidator::validate(
        &pool,
        x_api_key,
        auth_header,
        &request_path,
    ).await?;

    info!(api_key_id = %api_key_data.id, "API key validated");

    // Track API usage for analytics
    let mut tx = pool.begin().await
        .map_err(|e| ApiError::Database(format!("Failed to start transaction: {}", e)))?;

    ApiKeyValidator::track_usage(
        &mut tx,
        &api_key_data.id,
        &request_path,
        "GET",
        200,  // Status code
        None, // query_params
        None, // headers
        None, // No payload for GET request
        None, // No response yet
        None, // No error
    ).await?;

    tx.commit().await
        .map_err(|e| ApiError::Database(format!("Failed to commit analytics: {}", e)))?;

    // 3. Call shared domain logic (wallet-group-aware) and return. Only keys
    // with linked_wallet_breakdown see which wallets are linked.
    Ok(Json(domain::calculate_score_for_address_with_groups(
        &address,
        scorer_id,
        &pool,
        domain::LinkedWallets::for_api_key(&api_key_data),
    ).await?))
}
pub async fn chain_wallet_score_handler(
    Path((scorer_id, chain_id, address)): Path<(i64, i64, String)>,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<Json<domain::chain_wallet_scoring::ChainWalletScoreResponse>> {
    let address = address.to_lowercase();
    if !(1..=9_007_199_254_740_991).contains(&chain_id) || !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest("Invalid EIP-155 wallet identity".into()));
    }
    let request_path = format!("/v2/stamps/{scorer_id}/score/eip155/{chain_id}/{address}");
    let key = ApiKeyValidator::validate(
        &pool,
        headers.get("X-API-Key").and_then(|header| header.to_str().ok()),
        headers.get("Authorization").and_then(|header| header.to_str().ok()),
        &request_path,
    ).await?;
    if !(key.read_scores && key.linked_wallet_breakdown) {
        return Err(ApiError::Forbidden("Invalid permissions for action".into()));
    }
    let community_id: Option<i64> = sqlx::query_scalar(
        "SELECT COALESCE(
            (SELECT CASE WHEN COUNT(*) = 1 THEN MIN(id) END
             FROM account_community WHERE account_id = $1 AND external_scorer_id = $2),
            (SELECT id FROM account_community WHERE account_id = $1 AND id = $3)
         )",
    )
    .bind(key.account_id)
    .bind(scorer_id.to_string())
    .bind(scorer_id)
    .fetch_one(&pool)
    .await?;
    let community_id = community_id
        .ok_or_else(|| ApiError::NotFound("No scorer matches the given criteria".into()))?;
    let wallet = crate::account::linkage::WalletIdentity {
        address,
        chain_id: Some(chain_id),
    };
    let cluster = crate::account::linkage::get_wallet_cluster(&wallet)
        .await
        .map_err(|_| ApiError::Internal("Wallet linkage is unavailable".into()))?
        .ok_or_else(|| ApiError::NotFound("No active contract wallet link".into()))?;
    let score = domain::scoring::score_typed_cluster(&pool, community_id, &wallet, cluster).await?;
    Ok(Json(domain::chain_wallet_scoring::ChainWalletScoreResponse { chain_id, score }))
}
