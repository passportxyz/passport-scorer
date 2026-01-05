use axum::{
    extract::{Path, State},
    http::HeaderMap,
    Json,
};
use sqlx::PgPool;
use tracing::info;

use crate::api::error::{ApiError, ApiResult};
use crate::api::utils::is_valid_eth_address;
use crate::domain;
use crate::auth::api_key::ApiKeyValidator;
use crate::db::ceramic_cache::{
    bulk_insert_ceramic_cache_stamps, extract_providers, get_stamps_from_cache,
    soft_delete_stamps_by_provider,
};
use crate::models::v2_api::{
    AccountAPIKeySchema, AddStampsPayload, GetStampsWithV2ScoreResponse,
};

/// GET /internal/embed/validate-api-key
/// Validates partner API key and returns rate limit configuration
/// Authentication: API key via X-API-Key header
#[tracing::instrument(
    skip(pool, headers),
    fields(endpoint = "validate_api_key")
)]
pub async fn validate_api_key_handler(
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<Json<AccountAPIKeySchema>> {
    info!("Validating API key for embed");

    // Extract API key from headers
    let x_api_key = headers
        .get("X-API-Key")
        .and_then(|h| h.to_str().ok());
    let auth_header = headers
        .get("Authorization")
        .and_then(|h| h.to_str().ok());

    let request_path = "/internal/embed/validate-api-key";

    // Validate API key (will track usage internally)
    let api_key_data = ApiKeyValidator::validate(
        &pool,
        x_api_key,
        auth_header,
        request_path,
    )
    .await?;

    info!(api_key_id = %api_key_data.id, "API key validated");

    // Return rate limit info
    Ok(Json(AccountAPIKeySchema {
        embed_rate_limit: api_key_data.embed_rate_limit.clone(),
    }))
}

/// POST /internal/embed/stamps/{address}
/// Adds stamps to ceramic cache and returns updated score
/// Authentication: None (private ALB)
#[tracing::instrument(
    skip(pool, payload),
    fields(
        address = %address,
        scorer_id = payload.scorer_id,
        stamp_count = payload.stamps.len()
    )
)]
pub async fn add_stamps_handler(
    Path(address): Path<String>,
    State(pool): State<PgPool>,
    Json(payload): Json<AddStampsPayload>,
) -> ApiResult<Json<GetStampsWithV2ScoreResponse>> {
    info!("Adding stamps and scoring for embed");

    // Input validation
    let address = address.to_lowercase();
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest(
            "Invalid Ethereum address format".to_string(),
        ));
    }

    // Parse scorer_id explicitly (accepts string or integer from JSON)
    let scorer_id = payload
        .parse_scorer_id()
        .map_err(|e| ApiError::BadRequest(e))?;

    // Start transaction for ceramic cache operations
    let mut tx = pool
        .begin()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to start transaction: {}", e)))?;

    // 1. Extract providers for soft delete
    let providers = extract_providers(&payload.stamps);

    // 2. Soft delete existing stamps by provider
    soft_delete_stamps_by_provider(&address, &providers, &mut tx).await?;

    // 3. Bulk insert new stamps with source_app=EMBED (2)
    bulk_insert_ceramic_cache_stamps(
        &address,
        &payload.stamps,
        2, // EMBED source_app
        Some(scorer_id),
        &mut tx,
    )
    .await?;

    // Commit ceramic cache transaction
    tx.commit()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to commit transaction: {}", e)))?;

    info!("Ceramic cache operations completed");

    // 4. Score the address using domain logic
    // Embed endpoints do NOT include human points (matching Python behavior)
    let score_result = domain::calculate_score_for_address(
        &address,
        scorer_id,
        &pool,
    ).await;

    let score = score_result?;

    // 5. Get stamps from ceramic cache
    let stamps = get_stamps_from_cache(&pool, &address).await?;

    info!(stamp_count = stamps.len(), "Retrieved stamps from cache");

    Ok(Json(GetStampsWithV2ScoreResponse {
        success: true,
        stamps,
        score,
    }))
}

/// GET /internal/embed/score/{scorer_id}/{address}
/// Gets current score and stamps for an address
/// Authentication: None (private ALB)
#[tracing::instrument(
    skip(pool),
    fields(
        scorer_id = scorer_id,
        address = %address
    )
)]
pub async fn get_embed_score_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<GetStampsWithV2ScoreResponse>> {
    info!("Getting embed score");

    // Input validation
    let address = address.to_lowercase();
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest(
            "Invalid Ethereum address format".to_string(),
        ));
    }

    // 1. Get stamps from ceramic cache
    let stamps = get_stamps_from_cache(&pool, &address).await?;

    info!(stamp_count = stamps.len(), "Retrieved stamps from cache");

    // 2. Score the address using domain logic
    // Embed endpoints do NOT include human points (matching Python behavior)
    let score_result = domain::calculate_score_for_address(
        &address,
        scorer_id,
        &pool,
    ).await;

    let score = score_result?;

    Ok(Json(GetStampsWithV2ScoreResponse {
        success: true,
        stamps,
        score,
    }))
}
