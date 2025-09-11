use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use std::collections::{HashMap, HashSet};
use sqlx::PgPool;

use crate::models::{
    ScoringResult, StampData,
};
use crate::db::{DatabaseError, read_ops};
use crate::dedup::LifoResult;

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
    let scorer = read_ops::load_scorer_config(pool, community_id).await?;
    
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