// Internal API handlers - no authentication required (internal ALB only)
// These are thin handlers that orchestrate HTTP concerns and call domain logic

use axum::{
    extract::{Path, Query, State},
    Json,
};
use sqlx::PgPool;
use std::collections::HashMap;
use tracing::info;

use crate::api::error::{ApiError, ApiResult};
use crate::domain;
use crate::models::v2_api::V2ScoreResponse;

/// Helper function to validate Ethereum address format
fn is_valid_eth_address(address: &str) -> bool {
    address.len() == 42 && address.starts_with("0x") &&
    address[2..].chars().all(|c| c.is_ascii_hexdigit())
}

/// Internal score handler - no authentication needed
#[tracing::instrument(
    skip(pool),
    fields(
        scorer_id = scorer_id,
        address = %address
    )
)]
pub async fn internal_score_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<V2ScoreResponse>> {
    info!("Processing internal score request");

    // 1. Input validation
    let address = address.to_lowercase();
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest("Invalid Ethereum address format".to_string()));
    }

    // 2. No authentication needed (internal ALB)

    // 3. Call shared domain logic (no human points for internal endpoint)
    let result = domain::calculate_score_for_address(
        &address,
        scorer_id,
        &pool,
        false, // include_human_points
    ).await;

    // 4. Transform domain result to HTTP response
    match result {
        Ok(response) => Ok(Json(response)),
        Err(domain::DomainError::NotFound(msg)) => Err(ApiError::NotFound(msg)),
        Err(domain::DomainError::Validation(msg)) => Err(ApiError::BadRequest(msg)),
        Err(domain::DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        Err(domain::DomainError::Internal(msg)) => Err(ApiError::Internal(msg)),
    }
}

/// Internal weights handler
#[tracing::instrument(skip(pool))]
pub async fn internal_weights_handler(
    Query(params): Query<HashMap<String, String>>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<HashMap<String, f64>>> {
    info!("Processing internal weights request");

    // 1. Parse community_id from query params
    let scorer_id = params
        .get("community_id")
        .and_then(|s| s.parse::<i64>().ok());

    // 2. Call shared domain logic
    let result = domain::weights::get_scorer_weights(scorer_id, &pool).await;

    // 3. Transform result
    match result {
        Ok(weights) => Ok(Json(weights)),
        Err(domain::DomainError::NotFound(msg)) => Err(ApiError::NotFound(msg)),
        Err(domain::DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        Err(domain::DomainError::Internal(msg)) => Err(ApiError::Internal(msg)),
        _ => Err(ApiError::Internal("Unexpected error".to_string())),
    }
}

/// Internal ban check handler
#[tracing::instrument(skip(pool, _credentials))]
pub async fn internal_check_bans_handler(
    State(pool): State<PgPool>,
    Json(_credentials): Json<Vec<serde_json::Value>>,
) -> ApiResult<Json<Vec<domain::bans::BanCheckResult>>> {
    info!("Processing internal ban check request");

    // TODO: Implement in Phase 3
    // 1. Extract address from DID
    // 2. Extract hashes and providers
    // 3. Call domain::bans::check_credentials_for_bans

    Ok(Json(vec![]))
}

/// Internal revocation check handler
#[tracing::instrument(skip(pool, _payload))]
pub async fn internal_check_revocations_handler(
    State(pool): State<PgPool>,
    Json(_payload): Json<serde_json::Value>,
) -> ApiResult<Json<Vec<serde_json::Value>>> {
    info!("Processing internal revocation check request");

    // TODO: Implement in Phase 3
    Ok(Json(vec![]))
}

/// Internal allow list handler
#[tracing::instrument(skip(pool))]
pub async fn internal_allow_list_handler(
    Path((list, address)): Path<(String, String)>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::allow_list::AllowListResponse>> {
    info!("Processing internal allow list check");

    let result = domain::allow_list::check_allow_list_membership(&list, &address, &pool).await;

    match result {
        Ok(response) => Ok(Json(response)),
        Err(domain::DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        _ => Err(ApiError::Internal("Unexpected error".to_string())),
    }
}

/// Internal credential definition handler
#[tracing::instrument(skip(pool))]
pub async fn internal_credential_definition_handler(
    Path(provider_id): Path<String>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::allow_list::CredentialDefinitionResponse>> {
    info!("Processing internal credential definition request");

    // URL decode the provider_id
    let provider_id = provider_id.replace("%23", "#");

    let result = domain::allow_list::get_credential_definition(&provider_id, &pool).await;

    match result {
        Ok(response) => Ok(Json(response)),
        Err(domain::DomainError::NotFound(msg)) => Err(ApiError::NotFound(msg)),
        Err(domain::DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        _ => Err(ApiError::Internal("Unexpected error".to_string())),
    }
}

/// Internal GTC stake handler
#[tracing::instrument(skip(pool))]
pub async fn internal_stake_gtc_handler(
    Path(address): Path<String>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::stakes::StakeResponse>> {
    info!("Processing internal GTC stake request");

    let result = domain::stakes::get_gtc_stakes(&address, &pool).await;

    match result {
        Ok(response) => Ok(Json(response)),
        Err(domain::DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        _ => Err(ApiError::Internal("Unexpected error".to_string())),
    }
}

/// Internal legacy GTC stake handler
#[tracing::instrument(skip(pool))]
pub async fn internal_legacy_stake_handler(
    Path((address, round_id)): Path<(String, i32)>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::stakes::GtcEventsResponse>> {
    info!("Processing internal legacy GTC stake request");

    let result = domain::stakes::get_legacy_gtc_events(&address, round_id, &pool).await;

    match result {
        Ok(response) => Ok(Json(response)),
        Err(domain::DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        _ => Err(ApiError::Internal("Unexpected error".to_string())),
    }
}

/// Internal cgrants contributor statistics handler
#[tracing::instrument(skip(pool))]
pub async fn internal_cgrants_statistics_handler(
    Query(params): Query<HashMap<String, String>>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::cgrants::ContributorStatistics>> {
    info!("Processing internal cgrants statistics request");

    // Get address parameter (returns 422 if missing, matching Django Ninja behavior)
    let address = params.get("address")
        .ok_or_else(|| ApiError::BadRequest("Missing address parameter".to_string()))?;

    // Validate Ethereum address format (returns 400 for invalid address)
    if !is_valid_eth_address(address) {
        return Err(ApiError::BadRequest("Invalid address.".to_string()));
    }

    let result = domain::cgrants::get_contributor_statistics(address, &pool).await;

    match result {
        Ok(stats) => Ok(Json(stats)),
        Err(domain::DomainError::Validation(msg)) => Err(ApiError::BadRequest(msg)),
        Err(domain::DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        _ => Err(ApiError::Internal("Unexpected error".to_string())),
    }
}