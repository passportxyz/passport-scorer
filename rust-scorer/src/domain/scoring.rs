use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use std::collections::{HashMap, HashSet};
use sqlx::PgPool;

use crate::models::{
    ScoringResult, StampData, V2ScoreResponse,
};
use crate::db::DatabaseError;
use crate::db::queries;
use crate::domain::dedup::LifoResult;
use super::DomainError;

#[derive(Debug, Clone)]
pub struct ScorerConfig {
    pub weights: HashMap<String, Decimal>,
    pub threshold: Decimal,
}

/// Calculate the weighted score for a set of stamps after LIFO deduplication
/// 
/// # Arguments
/// * `address` - The Ethereum address being scored
/// * `community_id` - The community/scorer ID
/// * `lifo_result` - Result from LIFO deduplication containing valid and clashing stamps
/// * `pool` - Database connection pool for loading scorer configuration
/// 
/// # Returns
/// * `ScoringResult` - Complete scoring information including binary score, raw score, stamps, etc.
#[tracing::instrument(skip(lifo_result, pool), fields(address = %address, community_id = community_id))]
pub async fn calculate_score(
    address: &str,
    community_id: i64,
    lifo_result: LifoResult,
    pool: &PgPool,
) -> Result<ScoringResult, DatabaseError> {
    // Load scorer configuration
    let scorer_config = load_scorer_config(community_id, pool).await?;
    
    // Build the scoring result with deduplication and weight application
    let scoring_result = build_scoring_result(
        address,
        community_id,
        lifo_result,
        scorer_config,
    )?;
    
    Ok(scoring_result)
}

/// Load scorer configuration including weights and threshold
async fn load_scorer_config(
    community_id: i64,
    pool: &PgPool,
) -> Result<ScorerConfig, DatabaseError> {
    // Load scorer configuration (weights are always from scorer tables)
    let scorer = queries::load_scorer_config(pool, community_id).await?;
    
    let weights: HashMap<String, Decimal> = serde_json::from_value(scorer.weights)
        .map_err(|e| DatabaseError::QueryError(
            sqlx::Error::Decode(Box::new(e))
        ))?;
    
    Ok(ScorerConfig {
        weights,
        threshold: scorer.threshold,
    })
}

/// Build the complete scoring result from LIFO deduplication and scorer configuration
/// 
/// This function:
/// 1. Applies provider deduplication (only first stamp per provider contributes)
/// 2. Calculates weighted sum of valid stamps
/// 3. Determines binary score (1 if sum >= threshold, else 0)
/// 4. Tracks earliest expiration date from all stamps
/// 5. Constructs clean StampData objects for both valid and deduped stamps
pub fn build_scoring_result(
    address: &str,
    community_id: i64,
    lifo_result: LifoResult,
    scorer_config: ScorerConfig,
) -> Result<ScoringResult, DatabaseError> {
    let mut valid_stamps = Vec::new();
    let mut deduped_stamps = Vec::new();
    let mut raw_score = Decimal::from(0);
    let mut seen_providers = HashSet::new();
    let mut earliest_expiration: Option<DateTime<Utc>> = None;
    
    // Process valid stamps from LIFO (those that weren't deduped by nullifier clashes)
    for stamp_data in lifo_result.valid_stamps {
        // Apply provider deduplication - only first stamp per provider scores
        if seen_providers.insert(stamp_data.provider.clone()) {
            // First time seeing this provider, it contributes to score
            let weight = scorer_config.weights
                .get(&stamp_data.provider)
                .copied()
                .unwrap_or(Decimal::from(0));
            
            raw_score += weight;
            
            // Track earliest expiration
            match earliest_expiration {
                None => earliest_expiration = Some(stamp_data.expires_at),
                Some(exp) if stamp_data.expires_at < exp => {
                    earliest_expiration = Some(stamp_data.expires_at);
                },
                _ => {}
            }
            
            // Create StampData with weight applied
            valid_stamps.push(StampData {
                provider: stamp_data.provider,
                credential: stamp_data.credential,
                nullifiers: stamp_data.nullifiers,
                expires_at: stamp_data.expires_at,
                weight,
                was_deduped: false,
            });
        } else {
            // Duplicate provider - treat as deduped (score = 0)
            deduped_stamps.push(StampData {
                provider: stamp_data.provider,
                credential: stamp_data.credential,
                nullifiers: stamp_data.nullifiers,
                expires_at: stamp_data.expires_at,
                weight: Decimal::from(0),
                was_deduped: false, // Not deduped by LIFO, but by provider duplication
            });
        }
    }
    
    // Process stamps that were deduped by LIFO (nullifier clashes)
    for (provider, stamp_info) in lifo_result.clashing_stamps {
        // These stamps were deduped due to nullifier clashes
        // They have expiration dates from the clashing hash link
        deduped_stamps.push(StampData {
            provider: provider.clone(),
            credential: stamp_info.credential,
            nullifiers: stamp_info.nullifiers,
            expires_at: stamp_info.expires_at,  // Now using the proper expiration from hash link
            weight: Decimal::from(0),
            was_deduped: true,
        });
    }
    
    // Calculate binary score: 1 if raw_score >= threshold, else 0
    let binary_score = if raw_score >= scorer_config.threshold {
        Decimal::from(1)
    } else {
        Decimal::from(0)
    };
    
    Ok(ScoringResult {
        address: address.to_string(),
        community_id,
        binary_score,
        raw_score,
        threshold: scorer_config.threshold,
        valid_stamps,
        deduped_stamps,
        expires_at: earliest_expiration,
        timestamp: Utc::now(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::StampInfo;
    use rust_decimal_macros::dec;
    use serde_json::json;
    
    fn create_test_stamp(provider: &str, expires_days: i64) -> StampData {
        StampData {
            provider: provider.to_string(),
            credential: json!({"test": "credential"}),
            nullifiers: vec![format!("nullifier_{}", provider)],
            expires_at: Utc::now() + chrono::Duration::days(expires_days),
            weight: dec!(0), // Will be set during scoring
            was_deduped: false,
        }
    }
    
    fn create_test_config() -> ScorerConfig {
        let mut weights = HashMap::new();
        weights.insert("Google".to_string(), dec!(10.5));
        weights.insert("Twitter".to_string(), dec!(5.25));
        weights.insert("Github".to_string(), dec!(8.0));
        weights.insert("Discord".to_string(), dec!(3.75));
        
        ScorerConfig {
            weights,
            threshold: dec!(15.0),
        }
    }
    
    #[test]
    fn test_score_calculation_passing() {
        let config = create_test_config();
        let lifo_result = LifoResult {
            valid_stamps: vec![
                create_test_stamp("Google", 30),
                create_test_stamp("Twitter", 60),
                create_test_stamp("Github", 45),
            ],
            clashing_stamps: HashMap::new(),
            hash_links_processed: 3,
        };
        
        let result = build_scoring_result(
            "0x123",
            1,
            lifo_result,
            config,
        ).unwrap();
        
        // Raw score should be 10.5 + 5.25 + 8.0 = 23.75
        assert_eq!(result.raw_score, dec!(23.75));
        // Binary score should be 1 since 23.75 >= 15.0
        assert_eq!(result.binary_score, dec!(1));
        assert_eq!(result.valid_stamps.len(), 3);
        assert_eq!(result.deduped_stamps.len(), 0);
    }
    
    #[test]
    fn test_score_calculation_failing() {
        let config = create_test_config();
        let lifo_result = LifoResult {
            valid_stamps: vec![
                create_test_stamp("Twitter", 60),
                create_test_stamp("Discord", 45),
            ],
            clashing_stamps: HashMap::new(),
            hash_links_processed: 2,
        };
        
        let result = build_scoring_result(
            "0x456",
            2,
            lifo_result,
            config,
        ).unwrap();
        
        // Raw score should be 5.25 + 3.75 = 9.0
        assert_eq!(result.raw_score, dec!(9.0));
        // Binary score should be 0 since 9.0 < 15.0
        assert_eq!(result.binary_score, dec!(0));
        assert_eq!(result.valid_stamps.len(), 2);
    }
    
    #[test]
    fn test_provider_deduplication() {
        let config = create_test_config();
        let lifo_result = LifoResult {
            valid_stamps: vec![
                create_test_stamp("Google", 30),
                create_test_stamp("Google", 60), // Duplicate provider
                create_test_stamp("Twitter", 45),
            ],
            clashing_stamps: HashMap::new(),
            hash_links_processed: 3,
        };
        
        let result = build_scoring_result(
            "0x789",
            3,
            lifo_result,
            config,
        ).unwrap();
        
        // Only first Google stamp should count
        assert_eq!(result.raw_score, dec!(15.75)); // 10.5 + 5.25
        assert_eq!(result.binary_score, dec!(1)); // 15.75 >= 15.0
        assert_eq!(result.valid_stamps.len(), 2);
        assert_eq!(result.deduped_stamps.len(), 1); // Second Google stamp
        
        // Check that the deduped stamp has weight 0
        let deduped_google = result.deduped_stamps.iter()
            .find(|s| s.provider == "Google")
            .unwrap();
        assert_eq!(deduped_google.weight, dec!(0));
    }
    
    #[test]
    fn test_lifo_deduped_stamps() {
        let config = create_test_config();
        let mut clashing = HashMap::new();
        clashing.insert("Github".to_string(), StampInfo {
            credential: json!({"github": "credential"}),
            nullifiers: vec!["github_nullifier".to_string()],
            expires_at: Utc::now() + chrono::Duration::days(30),  // Expiration from hash link
        });
        
        let lifo_result = LifoResult {
            valid_stamps: vec![
                create_test_stamp("Google", 30),
                create_test_stamp("Twitter", 60),
            ],
            clashing_stamps: clashing,
            hash_links_processed: 3,
        };
        
        let result = build_scoring_result(
            "0xabc",
            4,
            lifo_result,
            config,
        ).unwrap();
        
        // Github shouldn't contribute to score (was deduped by LIFO)
        assert_eq!(result.raw_score, dec!(15.75)); // 10.5 + 5.25
        assert_eq!(result.binary_score, dec!(1));
        assert_eq!(result.valid_stamps.len(), 2);
        assert_eq!(result.deduped_stamps.len(), 1);
        
        // Check the deduped stamp
        let deduped_github = result.deduped_stamps.iter()
            .find(|s| s.provider == "Github")
            .unwrap();
        assert_eq!(deduped_github.weight, dec!(0));
        assert!(deduped_github.was_deduped);
    }
    
    #[test]
    fn test_earliest_expiration_tracking() {
        let config = create_test_config();
        let lifo_result = LifoResult {
            valid_stamps: vec![
                create_test_stamp("Google", 10), // Expires in 10 days
                create_test_stamp("Twitter", 30), // Expires in 30 days
                create_test_stamp("Github", 5), // Expires in 5 days - earliest
            ],
            clashing_stamps: HashMap::new(),
            hash_links_processed: 3,
        };
        
        let result = build_scoring_result(
            "0xdef",
            5,
            lifo_result,
            config,
        ).unwrap();
        
        // Should track the earliest expiration (Github at 5 days)
        assert!(result.expires_at.is_some());
        let expires = result.expires_at.unwrap();
        let expected_expiry = Utc::now() + chrono::Duration::days(5);
        
        // Check within 1 second tolerance (for test execution time)
        let diff = (expires - expected_expiry).num_seconds().abs();
        assert!(diff < 2, "Expiration time mismatch: {} seconds difference", diff);
    }
    
    #[test]
    fn test_unknown_provider_zero_weight() {
        let config = create_test_config();
        let lifo_result = LifoResult {
            valid_stamps: vec![
                create_test_stamp("Google", 30),
                create_test_stamp("UnknownProvider", 60), // Not in weights map
            ],
            clashing_stamps: HashMap::new(),
            hash_links_processed: 2,
        };
        
        let result = build_scoring_result(
            "0x111",
            6,
            lifo_result,
            config,
        ).unwrap();
        
        // Unknown provider should get weight 0
        assert_eq!(result.raw_score, dec!(10.5)); // Only Google counts
        assert_eq!(result.binary_score, dec!(0)); // 10.5 < 15.0
        
        // Both stamps should be in valid_stamps (not deduped)
        assert_eq!(result.valid_stamps.len(), 2);
        
        let unknown_stamp = result.valid_stamps.iter()
            .find(|s| s.provider == "UnknownProvider")
            .unwrap();
        assert_eq!(unknown_stamp.weight, dec!(0));
    }
    
    #[test]
    fn test_exact_threshold_passes() {
        let _config = create_test_config();
        let _lifo_result = LifoResult {
            valid_stamps: vec![
                create_test_stamp("Google", 30), // 10.5
                create_test_stamp("Discord", 30), // 3.75
                // Total: 14.25, but let's add a small stamp to reach exactly 15.0
            ],
            clashing_stamps: HashMap::new(),
            hash_links_processed: 2,
        };
        
        // Modify config to have a stamp that makes exactly threshold
        let mut weights = HashMap::new();
        weights.insert("Google".to_string(), dec!(10.0));
        weights.insert("Twitter".to_string(), dec!(5.0));
        let config_exact = ScorerConfig {
            weights,
            threshold: dec!(15.0),
        };
        
        let lifo_exact = LifoResult {
            valid_stamps: vec![
                create_test_stamp("Google", 30),
                create_test_stamp("Twitter", 30),
            ],
            clashing_stamps: HashMap::new(),
            hash_links_processed: 2,
        };
        
        let result = build_scoring_result(
            "0x222",
            7,
            lifo_exact,
            config_exact,
        ).unwrap();
        
        // Exactly at threshold should pass
        assert_eq!(result.raw_score, dec!(15.0));
        assert_eq!(result.binary_score, dec!(1)); // >= threshold passes
    }
}

/// Full scoring orchestration - this is what handlers should call
///
/// This implements the complete scoring flow:
/// 1. Load community configuration
/// 2. Upsert passport record
/// 3. Load and validate credentials from ceramic cache
/// 4. Apply LIFO deduplication
/// 5. Calculate score
/// 6. Persist to database
/// 7. Process human points (if enabled)
/// 8. Record events
pub async fn calculate_score_for_address(
    address: &str,
    scorer_id: i64,
    pool: &PgPool,
    include_human_points: bool,
) -> Result<V2ScoreResponse, DomainError> {
    use sqlx::{Postgres, Transaction};
    use crate::db::queries::{load_community, delete_stamps, bulk_insert_stamps, upsert_score};
    use crate::db::queries::stamps::{get_ceramic_cache_entries, get_latest_stamps_by_provider};
    use crate::db::queries::scoring::upsert_passport_record as upsert_passport;
    use crate::auth::credentials::validate_credentials_batch;
    use crate::models::internal::ValidStamp;
    use super::dedup::lifo_dedup;
    use super::human_points::process_human_points;

    // Start transaction for atomicity
    let mut tx: Transaction<'_, Postgres> = pool.begin().await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // 1. Load community configuration
    let community = load_community(pool, scorer_id).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // 2. Upsert passport record
    let passport_id = upsert_passport(&mut tx, address, scorer_id).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // 3. Load credentials from CeramicCache
    let ceramic_cache_entries = get_ceramic_cache_entries(pool, address).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    if ceramic_cache_entries.is_empty() {
        // TODO: Return zero score response
        return Err(DomainError::Internal("Zero score case not yet implemented".to_string()));
    }

    // 4. Get latest stamps per provider
    let latest_stamps = get_latest_stamps_by_provider(pool, address).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // 5. Validate credentials
    let stamp_values: Vec<serde_json::Value> = latest_stamps
        .iter()
        .map(|c| c.stamp.clone())
        .collect();

    let validated_credentials = validate_credentials_batch(&stamp_values, address).await
        .map_err(|e| DomainError::Validation(e.to_string()))?;

    let valid_stamps: Vec<ValidStamp> = validated_credentials
        .into_iter()
        .map(|vc| ValidStamp {
            provider: vc.provider,
            credential: vc.credential,
            nullifiers: vc.nullifiers,
            expires_at: vc.expires_at,
        })
        .collect();

    // 6. Load scorer weights
    let scorer_config = queries::load_scorer_config(pool, scorer_id).await
        .map_err(|e| DomainError::Database(e.to_string()))?;
    let weights: HashMap<String, Decimal> = serde_json::from_value(scorer_config.weights)
        .map_err(|e| DomainError::Internal(format!("Failed to parse weights: {}", e)))?;

    // 7. Apply LIFO deduplication
    let lifo_result = lifo_dedup(&valid_stamps, address, scorer_id, &weights, &mut tx).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // 8. Delete existing stamps and insert new ones
    delete_stamps(&mut tx, passport_id).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    if !lifo_result.valid_stamps.is_empty() {
        let stamps_for_insert: Vec<ValidStamp> = lifo_result.valid_stamps.iter()
            .map(|s| ValidStamp {
                provider: s.provider.clone(),
                credential: s.credential.clone(),
                nullifiers: s.nullifiers.clone(),
                expires_at: s.expires_at,
            })
            .collect();
        bulk_insert_stamps(&mut tx, passport_id, &stamps_for_insert).await
            .map_err(|e| DomainError::Database(e.to_string()))?;
    }

    // 9. Calculate score
    let scoring_result = calculate_score(address, scorer_id, lifo_result, pool).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // 10. Persist score
    let django_fields = scoring_result.to_django_score_fields();
    let _score_id = upsert_score(&mut tx, passport_id, &django_fields).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // 11. Process human points if enabled
    if include_human_points && community.human_points_program {
        process_human_points(
            &scoring_result,
            community.human_points_program,
            &mut tx,
        ).await.map_err(|e| DomainError::Database(e.to_string()))?;
    }

    // 12. Commit transaction
    tx.commit().await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // 13. Build response
    let mut response = scoring_result.to_v2_response();
    response.address = address.to_string();

    // 14. Add human points data if enabled and community has program
    if include_human_points && community.human_points_program {
        use super::human_points::{get_user_points_data, get_possible_points_data};

        // Get user's points data
        match get_user_points_data(address, pool).await {
            Ok(points_data) => {
                response.points_data = Some(points_data.clone());

                // Get possible points data using user's multiplier
                match get_possible_points_data(points_data.multiplier, pool).await {
                    Ok(possible_data) => {
                        response.possible_points_data = Some(possible_data);
                    }
                    Err(e) => {
                        tracing::warn!("Failed to get possible points data: {}", e);
                        // Don't fail the request, just skip possible points
                    }
                }
            }
            Err(e) => {
                tracing::warn!("Failed to get user points data: {}", e);
                // Don't fail the request, just skip points data
            }
        }
    }

    Ok(response)
}
