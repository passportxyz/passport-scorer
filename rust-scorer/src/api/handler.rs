use axum::{
    extract::{Path, Query, State},
    http::HeaderMap,
    Json,
};
use rust_decimal::Decimal;
use serde::Deserialize;
use sqlx::{PgPool, Postgres, Transaction};
use std::collections::HashMap;
use tracing::{error, info, instrument};

use crate::api::error::{ApiError, ApiResult};
use crate::auth::api_key::ApiKeyValidator;
use crate::auth::credentials::validate_credentials_batch;
use crate::db::read_ops::{
    get_latest_stamps_per_provider, load_ceramic_cache, load_community,
};
use crate::db::write_ops::{
    delete_stamps, insert_score_update_event, upsert_passport, upsert_score,
};
use crate::dedup::lifo::lifo_dedup;
use crate::human_points::processing::{
    get_possible_points_data, get_user_points_data, process_human_points,
};
use crate::models::v2_api::V2ScoreResponse;
use crate::scoring::calculate_score;

#[derive(Debug, Deserialize)]
pub struct ScoreQueryParams {
    #[serde(default)]
    pub include_human_points: bool,
}

#[instrument(skip(pool, headers), fields(scorer_id, address))]
pub async fn score_address_handler(
    Path((scorer_id, address)): Path<(i32, String)>,
    Query(params): Query<ScoreQueryParams>,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<Json<V2ScoreResponse>> {
    info!(
        include_human_points = params.include_human_points,
        "Processing score request"
    );

    // Input validation
    let address = address.to_lowercase();
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest("Invalid Ethereum address format".to_string()));
    }

    // Start a database transaction for atomicity
    let mut tx = pool.begin().await
        .map_err(|e| ApiError::Database(format!("Failed to start transaction: {}", e)))?;

    // Process the scoring request within the transaction
    let result = process_score_request(
        &address,
        scorer_id,
        params.include_human_points,
        &headers,
        &pool,
        &mut tx,
    ).await;

    // Handle the result - commit on success, rollback on error
    match result {
        Ok(response) => {
            tx.commit().await
                .map_err(|e| ApiError::Database(format!("Failed to commit transaction: {}", e)))?;
            Ok(response)
        }
        Err(e) => {
            // Transaction will be rolled back automatically when dropped
            error!("Score request failed: {:?}", e);
            Err(e)
        }
    }
}

async fn process_score_request(
    address: &str,
    scorer_id: i32,
    include_human_points: bool,
    headers: &HeaderMap,
    pool: &PgPool,
    tx: &mut Transaction<'_, Postgres>,
) -> ApiResult<Json<V2ScoreResponse>> {
    // 1. Validate API key and check permissions
    let x_api_key = headers.get("X-API-Key")
        .and_then(|h| h.to_str().ok());
    let auth_header = headers.get("Authorization")
        .and_then(|h| h.to_str().ok());
    
    let api_key_data = ApiKeyValidator::validate(
        pool,
        x_api_key,
        auth_header,
    ).await?;
    
    if !api_key_data.read_scores {
        return Err(ApiError::Unauthorized(
            "API key lacks read_scores permission".to_string()
        ));
    }

    // Track API usage for analytics
    ApiKeyValidator::track_usage(
        &mut **tx,
        api_key_data.id,
        &format!("/v2/stamps/{}/score/{}", scorer_id, address),
        "GET",
        200,  // Status code
        None, // query_params
        None, // headers
        None, // No payload for GET request
        None, // No response yet
        None, // No error
    ).await?;

    // 2. Check if community exists and get configuration
    let community = load_community(scorer_id, &mut **tx).await?;
    if community.deleted_at.is_some() {
        return Err(ApiError::NotFound(format!("Scorer {} not found", scorer_id)));
    }

    info!(
        human_points_enabled = community.human_points_program,
        "Community configuration loaded"
    );

    // 3. Upsert passport record
    let passport_id = upsert_passport(address, scorer_id, &mut **tx).await?;
    info!(passport_id = passport_id, "Passport record upserted");

    // 4. Load credentials from CeramicCache
    let ceramic_cache_entries = load_ceramic_cache(address, &mut **tx).await?;
    
    info!(
        total_credentials = ceramic_cache_entries.len(),
        "Loaded credentials from ceramic cache"
    );

    if ceramic_cache_entries.is_empty() {
        // No credentials - return zero score
        let zero_response = create_zero_score_response(
            address,
            scorer_id,
            passport_id,
            &mut **tx
        ).await?;
        
        return Ok(Json(zero_response));
    }

    // 5. Get latest stamps per provider (deduplicated by updated_at)
    let latest_stamps = get_latest_stamps_per_provider(&ceramic_cache_entries)?;
    
    info!(
        deduped_by_provider = latest_stamps.len(),
        "Deduplicated stamps by provider"
    );

    // 6. Validate credentials
    let valid_stamps = validate_credentials_batch(&latest_stamps, address).await
        .map_err(|e| ApiError::Validation(e.to_string()))?;
    
    info!(
        valid_count = valid_stamps.len(),
        "Validated credentials"
    );

    // 7. Apply LIFO deduplication
    let lifo_result = lifo_dedup(&valid_stamps, address, scorer_id, &mut **tx).await?;
    
    info!(
        valid_after_lifo = lifo_result.valid_stamps.len(),
        clashing = lifo_result.clashing_stamps.len(),
        "Applied LIFO deduplication"
    );

    // 8. Delete existing stamps and insert new valid ones
    delete_stamps(passport_id, &mut **tx).await?;
    
    // Insert valid stamps
    if !lifo_result.valid_stamps.is_empty() {
        crate::db::write_ops::bulk_insert_stamps(
            passport_id,
            &lifo_result.valid_stamps,
            &mut **tx,
        ).await?;
    }

    // 9. Calculate score
    let scoring_result = calculate_score(
        address,
        scorer_id,
        lifo_result.valid_stamps,
        lifo_result.clashing_stamps,
        &mut **tx,
    ).await?;

    info!(
        binary_score = %scoring_result.binary_score,
        raw_score = %scoring_result.raw_score,
        threshold = %scoring_result.threshold,
        "Calculated score"
    );

    // 10. Persist score using Django format
    let django_fields = scoring_result.to_django_score_fields();
    let score_id = upsert_score(passport_id, &django_fields, &mut **tx).await?;

    // 11. Record events
    // Record LIFO deduplication events
    if !scoring_result.deduped_stamps.is_empty() {
        crate::db::write_ops::insert_dedup_events(
            address,
            scorer_id,
            &scoring_result.deduped_stamps,
            &mut **tx,
        ).await?;
    }

    // Record score update event
    insert_score_update_event(
        address,
        scorer_id,
        score_id,
        passport_id,
        &django_fields,
        &mut **tx,
    ).await?;

    // 12. Process Human Points if enabled
    let mut points_data = None;
    let mut possible_points_data = None;

    if community.human_points_program && scoring_result.binary_score == Decimal::from(1) {
        // Process human points within transaction
        process_human_points(&scoring_result, true, &mut **tx).await?;
        
        info!("Processed human points");

        // Get points data for response if requested
        if include_human_points {
            points_data = Some(get_user_points_data(address, &mut **tx).await?);
            
            if let Some(ref pd) = points_data {
                possible_points_data = Some(get_possible_points_data(pd.multiplier, &mut **tx).await?);
            }
            
            info!("Loaded human points data for response");
        }
    }

    // 13. Build V2 response
    let mut response = scoring_result.to_v2_response();
    response.points_data = points_data;
    response.possible_points_data = possible_points_data;

    info!(
        score = response.score.as_ref().unwrap_or(&"0.00000".to_string()),
        passing = response.passing_score,
        "Score request completed successfully"
    );

    Ok(Json(response))
}

async fn create_zero_score_response(
    address: &str,
    scorer_id: i32,
    passport_id: i32,
    tx: &mut Transaction<'_, Postgres>,
) -> ApiResult<V2ScoreResponse> {
    let zero_response = V2ScoreResponse {
        address: address.to_string(),
        score: Some("0.00000".to_string()),
        passing_score: false,
        threshold: "0.00000".to_string(),
        last_score_timestamp: Some(chrono::Utc::now().to_rfc3339()),
        expiration_timestamp: None,
        error: None,
        stamps: HashMap::new(),
        points_data: None,
        possible_points_data: None,
    };

    // Save zero score to database
    let score_fields = crate::models::django::DjangoScoreFields {
        score: Decimal::ZERO,
        status: "DONE".to_string(),
        last_score_timestamp: chrono::Utc::now(),
        expiration_date: None,
        error: None,
        evidence: serde_json::json!({
            "type": "ThresholdScoreCheck",
            "success": false,
            "rawScore": "0",
            "threshold": "0"
        }),
        stamp_scores: serde_json::json!({}),
        stamps: serde_json::json!({}),
    };

    let score_id = upsert_score(passport_id, &score_fields, tx).await?;
    
    // Record score update event
    insert_score_update_event(
        address,
        scorer_id,
        score_id,
        passport_id,
        &score_fields,
        tx,
    ).await?;

    Ok(zero_response)
}

fn is_valid_eth_address(address: &str) -> bool {
    // Check if it's a valid Ethereum address
    // Must be 42 characters (0x + 40 hex chars)
    if address.len() != 42 {
        return false;
    }
    
    if !address.starts_with("0x") {
        return false;
    }
    
    // Check if remaining characters are valid hex
    address[2..].chars().all(|c| c.is_ascii_hexdigit())
}