// External API handlers - require API key authentication
// These are thin handlers that orchestrate HTTP concerns and call domain logic

use axum::{
    extract::{Path, Query, State},
    http::HeaderMap,
    Json,
};
use sqlx::PgPool;
use std::collections::HashMap;
use tracing::info;

use crate::api::error::{ApiError, ApiResult};
use crate::auth::api_key::ApiKeyValidator;
use crate::domain;
use crate::models::v2_api::V2ScoreResponse;

/// Helper function to validate Ethereum address format
fn is_valid_eth_address(address: &str) -> bool {
    address.len() == 42 && address.starts_with("0x") &&
    address[2..].chars().all(|c| c.is_ascii_hexdigit())
}

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
    Query(params): Query<HashMap<String, String>>,
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

    // 3. Check for human points parameter
    let include_human_points = params
        .get("include_human_points")
        .map(|v| v == "true")
        .unwrap_or(false);

    // 4. Call shared domain logic
    let result = domain::calculate_score_for_address(
        &address,
        scorer_id,
        &pool,
        include_human_points,
    ).await;

    // 5. Transform domain result to HTTP response
    match result {
        Ok(response) => Ok(Json(response)),
        Err(domain::DomainError::NotFound(msg)) => Err(ApiError::NotFound(msg)),
        Err(domain::DomainError::Validation(msg)) => Err(ApiError::BadRequest(msg)),
        Err(domain::DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        Err(domain::DomainError::Internal(msg)) => Err(ApiError::Internal(msg)),
    }
}