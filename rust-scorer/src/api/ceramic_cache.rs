use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use sqlx::PgPool;
use tracing::info;

use crate::api::error::{ApiError, ApiResult};
use crate::api::utils::is_valid_eth_address;
use crate::domain;
use crate::domain::DomainError;
use crate::auth::jwt::{extract_jwt_from_header, validate_jwt_and_extract_address};
use crate::db::ceramic_cache::{
    bulk_insert_ceramic_cache_stamps, get_stamps_from_cache,
    soft_delete_stamps_by_provider,
};
use crate::models::v2_api::{CacheStampPayload, GetStampsWithInternalV2ScoreResponse, GetStampResponse, InternalV2ScoreResponse};

/// Check if the request should use Rust scorer based on header
/// Returns true if X-Use-Rust-Scorer header is present and equals "true"
fn should_use_rust(headers: &HeaderMap) -> bool {
    headers
        .get("X-Use-Rust-Scorer")
        .and_then(|v| v.to_str().ok())
        .map(|v| v == "true")
        .unwrap_or(false)
}

/// Get CERAMIC_CACHE_SCORER_ID from environment with fallback to 335
fn get_ceramic_cache_scorer_id() -> Result<i64, ApiError> {
    std::env::var("CERAMIC_CACHE_SCORER_ID")
        .unwrap_or_else(|_| "335".to_string())
        .parse::<i64>()
        .map_err(|e| ApiError::Internal(format!("Invalid CERAMIC_CACHE_SCORER_ID: {}", e)))
}

/// POST /ceramic-cache/stamps/bulk
/// Adds stamps to ceramic cache and returns updated score with human points
/// Authentication: JWT token with DID claim
/// Routing: Requires X-Use-Rust-Scorer: true header
#[tracing::instrument(
    skip(pool, headers, payload),
    fields(
        endpoint = "ceramic_cache_stamps_bulk",
        stamp_count = payload.len(),
        has_rust_header = should_use_rust(&headers)
    )
)]
pub async fn ceramic_cache_add_stamps(
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(payload): Json<Vec<CacheStampPayload>>,
) -> ApiResult<(StatusCode, Json<GetStampsWithInternalV2ScoreResponse>)> {
    info!("Processing ceramic-cache add stamps request");

    // Check for Rust routing header
    if !should_use_rust(&headers) {
        tracing::debug!("X-Use-Rust-Scorer header not set, returning 404 to fall back to Python");
        return Err(ApiError::NotFound(
            "Rust scorer not enabled for this request".to_string(),
        ));
    }

    // Extract and validate JWT token
    let auth_header = headers.get("Authorization").and_then(|h| h.to_str().ok());
    let token = extract_jwt_from_header(auth_header)?;
    let address = validate_jwt_and_extract_address(token)?;

    info!(address = %address, "JWT validated, extracted address");

    // Input validation
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest(
            "Invalid Ethereum address format in JWT".to_string(),
        ));
    }

    // Get scorer ID from environment
    let scorer_id = get_ceramic_cache_scorer_id()?;

    // Start transaction for ceramic cache operations
    let mut tx = pool
        .begin()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to start transaction: {}", e)))?;

    // 1. Extract providers for soft delete
    let providers: Vec<String> = payload
        .iter()
        .map(|p| p.provider.clone())
        .collect();

    // 2. Soft delete existing stamps by provider
    soft_delete_stamps_by_provider(&address, &providers, &mut tx).await?;

    // 3. Extract stamps (only those with stamp field present)
    let stamps: Vec<serde_json::Value> = payload
        .iter()
        .filter_map(|p| p.stamp.clone())
        .collect();

    // 4. Bulk insert new stamps with source_app=PASSPORT (1)
    if !stamps.is_empty() {
        bulk_insert_ceramic_cache_stamps(
            &address,
            &stamps,
            1, // PASSPORT source_app
            Some(scorer_id),
            &mut tx,
        )
        .await?;
    }

    // Commit ceramic cache transaction
    tx.commit()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to commit transaction: {}", e)))?;

    info!("Ceramic cache operations completed");

    // 5. Score the address using domain logic
    // Ceramic cache endpoints include human points (matching Python behavior)
    let score_result = domain::calculate_score_for_address(
        &address,
        scorer_id,
        &pool,
        true, // include_human_points
    ).await;

    let score = match score_result {
        Ok(response) => response,
        Err(DomainError::NotFound(msg)) => return Err(ApiError::NotFound(msg)),
        Err(DomainError::Validation(msg)) => return Err(ApiError::BadRequest(msg)),
        Err(DomainError::Database(msg)) => return Err(ApiError::Database(msg)),
        Err(DomainError::Internal(msg)) => return Err(ApiError::Internal(msg)),
    };

    // 6. Get updated stamps from cache
    let cached_stamps = get_stamps_from_cache(&pool, &address).await?;

    info!(stamp_count = cached_stamps.len(), "Retrieved updated stamps");

    // Return 201 Created to match Python behavior
    Ok((
        StatusCode::CREATED,
        Json(GetStampsWithInternalV2ScoreResponse {
            success: true,
            stamps: cached_stamps,
            score,
        }),
    ))
}

/// GET /ceramic-cache/score/{address}
/// Gets current score with human points for an address
/// Authentication: JWT token with DID claim
/// Routing: Requires X-Use-Rust-Scorer: true header
/// Returns: Just the score (InternalV2ScoreResponse), not stamps array
#[tracing::instrument(
    skip(pool, headers),
    fields(
        endpoint = "ceramic_cache_get_score",
        address = %address,
        has_rust_header = should_use_rust(&headers)
    )
)]
pub async fn ceramic_cache_get_score(
    Path(address): Path<String>,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<Json<InternalV2ScoreResponse>> {
    info!("Processing ceramic-cache get score request");

    // Check for Rust routing header
    if !should_use_rust(&headers) {
        tracing::debug!("X-Use-Rust-Scorer header not set, returning 404 to fall back to Python");
        return Err(ApiError::NotFound(
            "Rust scorer not enabled for this request".to_string(),
        ));
    }

    // Extract and validate JWT token
    let auth_header = headers.get("Authorization").and_then(|h| h.to_str().ok());
    let token = extract_jwt_from_header(auth_header)?;
    let jwt_address = validate_jwt_and_extract_address(token)?;

    // Validate that the address in the path matches the address in the JWT
    let path_address = address.to_lowercase();
    if path_address != jwt_address {
        return Err(ApiError::Unauthorized(
            "Address in path does not match address in JWT".to_string(),
        ));
    }

    info!(address = %jwt_address, "JWT validated, address matches");

    // Input validation
    if !is_valid_eth_address(&jwt_address) {
        return Err(ApiError::BadRequest(
            "Invalid Ethereum address format".to_string(),
        ));
    }

    // Get scorer ID from environment
    let scorer_id = get_ceramic_cache_scorer_id()?;

    // Score the address using domain logic
    // Ceramic cache endpoints include human points (matching Python behavior)
    let score_result = domain::calculate_score_for_address(
        &jwt_address,
        scorer_id,
        &pool,
        true, // include_human_points
    ).await;

    let score = match score_result {
        Ok(response) => response,
        Err(DomainError::NotFound(msg)) => return Err(ApiError::NotFound(msg)),
        Err(DomainError::Validation(msg)) => return Err(ApiError::BadRequest(msg)),
        Err(DomainError::Database(msg)) => return Err(ApiError::Database(msg)),
        Err(DomainError::Internal(msg)) => return Err(ApiError::Internal(msg)),
    };

    // Return just the score (Python returns InternalV2ScoreResponse, not GetStampsWithInternalV2ScoreResponse)
    Ok(Json(score))
}

/// PATCH /ceramic-cache/stamps/bulk
/// Updates stamps in ceramic cache (soft delete + recreate) and returns updated score with human points
/// Authentication: JWT token with DID claim
/// Routing: Requires X-Use-Rust-Scorer: true header
///
/// Logic: Soft deletes all providers in payload, then recreates only those with stamp field present
/// Returns: 200 OK with stamps and score
#[tracing::instrument(
    skip(pool, headers, payload),
    fields(
        endpoint = "ceramic_cache_patch_stamps",
        stamp_count = payload.len(),
        has_rust_header = should_use_rust(&headers)
    )
)]
pub async fn ceramic_cache_patch_stamps(
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(payload): Json<Vec<CacheStampPayload>>,
) -> ApiResult<Json<GetStampsWithInternalV2ScoreResponse>> {
    info!("Processing ceramic-cache patch stamps request");

    // Check for Rust routing header
    if !should_use_rust(&headers) {
        tracing::debug!("X-Use-Rust-Scorer header not set, returning 404 to fall back to Python");
        return Err(ApiError::NotFound(
            "Rust scorer not enabled for this request".to_string(),
        ));
    }

    // Extract and validate JWT token
    let auth_header = headers.get("Authorization").and_then(|h| h.to_str().ok());
    let token = extract_jwt_from_header(auth_header)?;
    let address = validate_jwt_and_extract_address(token)?;

    info!(address = %address, "JWT validated, extracted address");

    // Input validation
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest(
            "Invalid Ethereum address format in JWT".to_string(),
        ));
    }

    // Get scorer ID from environment
    let scorer_id = get_ceramic_cache_scorer_id()?;

    // Start transaction for ceramic cache operations
    let mut tx = pool
        .begin()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to start transaction: {}", e)))?;

    // 1. Extract providers for soft delete (all providers in payload)
    let providers: Vec<String> = payload
        .iter()
        .map(|p| p.provider.clone())
        .collect();

    // 2. Soft delete existing stamps by provider (for all providers in payload)
    soft_delete_stamps_by_provider(&address, &providers, &mut tx).await?;

    // 3. Extract stamps (only those with stamp field present - recreate these)
    let stamps: Vec<serde_json::Value> = payload
        .iter()
        .filter_map(|p| p.stamp.clone())
        .collect();

    // 4. Bulk insert new stamps with source_app=PASSPORT (1) - only for stamps with stamp field
    if !stamps.is_empty() {
        bulk_insert_ceramic_cache_stamps(
            &address,
            &stamps,
            1, // PASSPORT source_app
            Some(scorer_id),
            &mut tx,
        )
        .await?;
    }

    // Commit ceramic cache transaction
    tx.commit()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to commit transaction: {}", e)))?;

    info!("Ceramic cache PATCH operations completed");

    // 5. Score the address using domain logic
    // Ceramic cache endpoints include human points (matching Python behavior)
    let score_result = domain::calculate_score_for_address(
        &address,
        scorer_id,
        &pool,
        true, // include_human_points
    ).await;

    let score = match score_result {
        Ok(response) => response,
        Err(DomainError::NotFound(msg)) => return Err(ApiError::NotFound(msg)),
        Err(DomainError::Validation(msg)) => return Err(ApiError::BadRequest(msg)),
        Err(DomainError::Database(msg)) => return Err(ApiError::Database(msg)),
        Err(DomainError::Internal(msg)) => return Err(ApiError::Internal(msg)),
    };

    // 6. Get updated stamps from cache
    let cached_stamps = get_stamps_from_cache(&pool, &address).await?;

    info!(stamp_count = cached_stamps.len(), "Retrieved updated stamps after PATCH");

    // Return 200 OK (PATCH uses 200, not 201)
    Ok(Json(GetStampsWithInternalV2ScoreResponse {
        success: true,
        stamps: cached_stamps,
        score,
    }))
}

/// DELETE /ceramic-cache/stamps/bulk
/// Deletes stamps from ceramic cache (soft delete only) and returns remaining stamps (no score)
/// Authentication: JWT token with DID claim
/// Routing: Requires X-Use-Rust-Scorer: true header
///
/// Logic: Soft deletes all providers in payload, does not recreate any stamps
/// Returns: 200 OK with remaining stamps (NOTE: Python schema says GetStampResponse which doesn't include score!)
#[tracing::instrument(
    skip(pool, headers, payload),
    fields(
        endpoint = "ceramic_cache_delete_stamps",
        stamp_count = payload.len(),
        has_rust_header = should_use_rust(&headers)
    )
)]
pub async fn ceramic_cache_delete_stamps(
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(payload): Json<Vec<CacheStampPayload>>,
) -> ApiResult<Json<GetStampResponse>> {
    info!("Processing ceramic-cache delete stamps request");

    // Check for Rust routing header
    if !should_use_rust(&headers) {
        tracing::debug!("X-Use-Rust-Scorer header not set, returning 404 to fall back to Python");
        return Err(ApiError::NotFound(
            "Rust scorer not enabled for this request".to_string(),
        ));
    }

    // Extract and validate JWT token
    let auth_header = headers.get("Authorization").and_then(|h| h.to_str().ok());
    let token = extract_jwt_from_header(auth_header)?;
    let address = validate_jwt_and_extract_address(token)?;

    info!(address = %address, "JWT validated, extracted address");

    // Input validation
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest(
            "Invalid Ethereum address format in JWT".to_string(),
        ));
    }

    // Start transaction for ceramic cache operations
    let mut tx = pool
        .begin()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to start transaction: {}", e)))?;

    // 1. Extract providers for soft delete
    let providers: Vec<String> = payload
        .iter()
        .map(|p| p.provider.clone())
        .collect();

    // 2. Soft delete stamps by provider (no recreation for DELETE)
    soft_delete_stamps_by_provider(&address, &providers, &mut tx).await?;

    // Commit ceramic cache transaction
    tx.commit()
        .await
        .map_err(|e| ApiError::Database(format!("Failed to commit transaction: {}", e)))?;

    info!("Ceramic cache DELETE operations completed");

    // 3. Get remaining stamps from cache (no scoring for DELETE - Python returns GetStampResponse without score)
    let cached_stamps = get_stamps_from_cache(&pool, &address).await?;

    info!(stamp_count = cached_stamps.len(), "Retrieved remaining stamps after DELETE");

    // Return 200 OK with just stamps (Python's GetStampResponse schema doesn't include score!)
    Ok(Json(GetStampResponse {
        success: true,
        stamps: cached_stamps,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::HeaderValue;

    #[test]
    fn test_should_use_rust_true() {
        let mut headers = HeaderMap::new();
        headers.insert("X-Use-Rust-Scorer", HeaderValue::from_static("true"));
        assert!(should_use_rust(&headers));
    }

    #[test]
    fn test_should_use_rust_false() {
        let mut headers = HeaderMap::new();
        headers.insert("X-Use-Rust-Scorer", HeaderValue::from_static("false"));
        assert!(!should_use_rust(&headers));
    }

    #[test]
    fn test_should_use_rust_missing() {
        let headers = HeaderMap::new();
        assert!(!should_use_rust(&headers));
    }

    #[test]
    fn test_should_use_rust_invalid_value() {
        let mut headers = HeaderMap::new();
        headers.insert("X-Use-Rust-Scorer", HeaderValue::from_static("invalid"));
        assert!(!should_use_rust(&headers));
    }

    // Note: Environment variable tests are not included here because set_var/remove_var
    // affect the global process environment and can't be safely tested in parallel.
    // The get_ceramic_cache_scorer_id function is simple enough that manual testing
    // or integration tests are sufficient.
}
