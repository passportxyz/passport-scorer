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

    // 4. Score the address using existing scoring logic
    // Create a new transaction for scoring operations
    let mut score_tx = pool
        .begin()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to start transaction: {}", e)))?;

    // TODO: Migrate to use domain::calculate_score_for_address
    // MIGRATION REFERENCE - This was the old scoring flow:
    /*
    // 1. Check if community exists and get configuration
    let community = load_community(pool, scorer_id).await?;

    // 2. Upsert passport record
    let passport_id = upsert_passport(tx, address, scorer_id).await?;

    // 3. Load credentials from CeramicCache
    let ceramic_cache_entries = load_ceramic_cache(pool, address).await?;

    if ceramic_cache_entries.is_empty() {
        return zero_score_response...
    }

    // 4. Get latest stamps per provider (deduplicated)
    let latest_stamps = get_latest_stamps_per_provider(pool, address).await?;

    // 5. Validate credentials
    let stamp_values: Vec<serde_json::Value> = latest_stamps
        .iter()
        .map(|c| c.stamp.clone())
        .collect();
    let validated_credentials = validate_credentials_batch(&stamp_values, address).await?;

    // 6. Load scorer weights
    let scorer_config = load_scorer_config(pool, scorer_id).await?;
    let weights: HashMap<String, Decimal> = serde_json::from_value(scorer_config.weights)?;

    // 7. Apply LIFO deduplication
    let lifo_result = lifo_dedup(&valid_stamps, address, scorer_id, &weights, tx).await?;

    // 8. Delete existing stamps and insert new valid ones
    delete_stamps(tx, passport_id).await?;
    if !lifo_result.valid_stamps.is_empty() {
        bulk_insert_stamps(tx, passport_id, &stamps_for_insert).await?;
    }

    // 9. Calculate score
    let scoring_result = calculate_score(address, scorer_id, lifo_result, pool).await?;

    // 10. Persist score
    let django_fields = scoring_result.to_django_score_fields();
    let score_id = upsert_score(tx, passport_id, &django_fields).await?;

    // 11. Record events (LIFO dedup and score update)
    if !scoring_result.deduped_stamps.is_empty() {
        insert_dedup_events(tx, address, scorer_id, &clashing_stamps_map).await?;
    }
    insert_score_update_event(tx, address, scorer_id, score_id).await?;

    // 12. Process human points if enabled
    if community.human_points_program {
        process_human_points(...).await?;
    }

    // 13. Build response
    let response = scoring_result.to_v2_response(address);
    */

    Err(ApiError::Internal(
        "Embed endpoints need migration to new architecture".to_string()
    ))
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

    // 2. Score the address using existing scoring logic
    let mut tx = pool
        .begin()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to start transaction: {}", e)))?;

    return Err(ApiError::Internal("Needs migration".to_string()));

    // Commit transaction
    tx.commit()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to commit transaction: {}", e)))?;

    Ok(Json(GetStampsWithV2ScoreResponse {
        success: true,
        stamps,
        score: todo!(), // Needs migration
    }))
}
