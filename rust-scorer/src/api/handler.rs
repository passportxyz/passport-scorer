use axum::{
    extract::{Path, Query, State},
    http::HeaderMap,
    Json,
};
use rust_decimal::Decimal;
use serde::Deserialize;
use sqlx::{PgPool, Postgres, Transaction};
use std::collections::HashMap;
use tracing::{error, info};

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

#[tracing::instrument(
    skip(pool, headers),
    fields(
        scorer_id = scorer_id,
        address = %address,
        include_human_points = params.include_human_points
    )
)]
pub async fn score_address_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    Query(params): Query<ScoreQueryParams>,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> ApiResult<Json<V2ScoreResponse>> {
    info!("Processing score request");

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

#[tracing::instrument(
    skip(headers, pool, tx),
    fields(
        address = %address,
        scorer_id = scorer_id,
        include_human_points = _include_human_points
    )
)]
async fn process_score_request(
    address: &str,
    scorer_id: i64,
    _include_human_points: bool,  // Not used - we always include human points data
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
        tx,
        &api_key_data.id,
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
    let community = load_community(pool, scorer_id).await?;
    // Note: DjangoCommunity doesn't have deleted_at field

    info!(
        human_points_enabled = community.human_points_program,
        "Community configuration loaded"
    );

    // 3. Upsert passport record
    let passport_id = upsert_passport(tx, address, scorer_id).await?;
    info!(passport_id = passport_id, "Passport record upserted");

    // 4. Load credentials from CeramicCache
    let ceramic_cache_entries = load_ceramic_cache(pool, address).await?;
    
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
            tx
        ).await?;
        
        return Ok(Json(zero_response));
    }

    // 5. Get latest stamps per provider (deduplicated by updated_at)
    let latest_stamps = get_latest_stamps_per_provider(pool, address).await?;
    
    info!(
        deduped_by_provider = latest_stamps.len(),
        "Deduplicated stamps by provider"
    );
    

    // 6. Validate credentials - extract stamp JSON from ceramic cache
    let stamp_values: Vec<serde_json::Value> = latest_stamps
        .iter()
        .map(|c| c.stamp.clone())
        .collect();
    
    let validated_credentials = validate_credentials_batch(&stamp_values, address).await
        .map_err(|e| ApiError::Validation(e.to_string()))?;
    
    // Convert ValidatedCredential to ValidStamp for internal use
    let valid_stamps: Vec<crate::models::internal::ValidStamp> = validated_credentials
        .into_iter()
        .map(|vc| crate::models::internal::ValidStamp {
            provider: vc.provider,
            credential: vc.credential,
            nullifiers: vc.nullifiers,
            expires_at: vc.expires_at,
        })
        .collect();
    
    info!(
        valid_count = valid_stamps.len(),
        "Validated credentials"
    );

    // 7. Load scorer weights first (needed for LIFO)
    let scorer_config = crate::db::read_ops::load_scorer_config(pool, scorer_id).await?;
    let weights: HashMap<String, Decimal> = serde_json::from_value(scorer_config.weights.clone())
        .map_err(|e| ApiError::Internal(format!("Failed to parse weights: {}", e)))?;
    
    // 8. Apply LIFO deduplication
    let lifo_result = lifo_dedup(&valid_stamps, address, scorer_id, &weights, tx).await?;
    
    info!(
        valid_after_lifo = lifo_result.valid_stamps.len(),
        clashing = lifo_result.clashing_stamps.len(),
        "Applied LIFO deduplication"
    );

    // 9. Delete existing stamps and insert new valid ones
    delete_stamps(tx, passport_id).await?;
    
    // Insert valid stamps
    if !lifo_result.valid_stamps.is_empty() {
        // Convert StampData back to ValidStamp for bulk insert
        let stamps_for_insert: Vec<crate::models::internal::ValidStamp> = lifo_result.valid_stamps
            .iter()
            .map(|sd| crate::models::internal::ValidStamp {
                provider: sd.provider.clone(),
                credential: sd.credential.clone(),
                nullifiers: sd.nullifiers.clone(),
                expires_at: sd.expires_at,
            })
            .collect();
        
        crate::db::write_ops::bulk_insert_stamps(
            tx,
            passport_id,
            &stamps_for_insert,
        ).await?;
    }

    // 10. Calculate score
    let scoring_result = calculate_score(
        address,
        scorer_id,
        lifo_result,
        pool,
    ).await?;

    info!(
        binary_score = %scoring_result.binary_score,
        raw_score = %scoring_result.raw_score,
        threshold = %scoring_result.threshold,
        "Calculated score"
    );

    // 11. Persist score using Django format
    let django_fields = scoring_result.to_django_score_fields();
    let score_id = upsert_score(tx, passport_id, &django_fields).await?;

    // 12. Record events
    // Record LIFO deduplication events
    if !scoring_result.deduped_stamps.is_empty() {
        // Convert deduped stamps to the format expected by insert_dedup_events
        let mut clashing_stamps_map = HashMap::new();
        for stamp in &scoring_result.deduped_stamps {
            clashing_stamps_map.insert(
                stamp.provider.clone(),
                crate::models::internal::StampInfo {
                    nullifiers: stamp.nullifiers.clone(),
                    credential: stamp.credential.clone(),
                    expires_at: stamp.expires_at,
                },
            );
        }
        
        crate::db::write_ops::insert_dedup_events(
            tx,
            address,
            scorer_id,
            &clashing_stamps_map,
        ).await?;
    }

    // Record score update event
    insert_score_update_event(
        tx,
        address,
        scorer_id,
        score_id,
        passport_id,
        &django_fields,
    ).await?;

    // 13. Process Human Points if enabled
    let mut points_data = None;
    let mut possible_points_data = None;

    if community.human_points_program && scoring_result.binary_score == Decimal::from(1) {
        // Process human points within transaction
        process_human_points(&scoring_result, true, tx).await?;

        info!("Processed human points");

        // Always include human points data in response
        points_data = Some(get_user_points_data(address, pool).await?);

        if let Some(ref pd) = points_data {
            possible_points_data = Some(get_possible_points_data(pd.multiplier, pool).await?);
        }

        info!("Loaded human points data for response");
    }

    // 14. Build V2 response
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
    scorer_id: i64,
    passport_id: i64,
    tx: &mut Transaction<'_, Postgres>,
) -> ApiResult<V2ScoreResponse> {
    let zero_response = V2ScoreResponse {
        address: address.to_string(),
        score: Some("0.00000".to_string()),
        passing_score: false,
        last_score_timestamp: Some(crate::models::v2_api::format_datetime_python(chrono::Utc::now())),
        expiration_timestamp: None,
        threshold: "0.00000".to_string(),
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
        stamps: HashMap::new(),
    };

    let score_id = upsert_score(tx, passport_id, &score_fields).await?;
    
    // Record score update event
    insert_score_update_event(
        tx,
        address,
        scorer_id,
        score_id,
        passport_id,
        &score_fields,
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