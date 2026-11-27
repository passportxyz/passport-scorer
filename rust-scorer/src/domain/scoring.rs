use crate::account::linkage::{WalletCluster, WalletIdentity, get_wallet_cluster};
use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use std::collections::{HashMap, HashSet};
use sqlx::PgPool;

use crate::models::{
    ScoringResult, StampData, V2ScoreResponse,
};
use crate::models::v2_api::{LinkedScoreResponse, V2StampScoreResponse, format_decimal_5};
use crate::models::django::{DjangoScoreFields, DjangoStampScore};
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
) -> Result<V2ScoreResponse, DomainError> {
    let (response, _) = score_address(address, scorer_id, pool, SaveScore::Yes).await?;
    Ok(response)
}

/// Whether `score_address` stores the wallet's Score row and SCORE_UPDATE event.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SaveScore {
    Yes,
    /// Wallet-group scoring: the rows are saved once, after the merge
    /// (`save_group_scores`). Stamps, dedup links and human points are still saved.
    No,
}

/// Score one wallet. Returns the response and the score timestamp.
async fn score_address(
    address: &str,
    scorer_id: i64,
    pool: &PgPool,
    save_score: SaveScore,
) -> Result<(V2ScoreResponse, DateTime<Utc>), DomainError> {
    use sqlx::{Postgres, Transaction};
    use crate::db::queries::{load_community, delete_stamps, bulk_insert_stamps};
    use crate::db::queries::stamps::get_latest_stamps_by_provider;
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

    // 3. Get latest stamps per provider (handles empty case naturally)
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

    // 10. Persist score and its SCORE_UPDATE event
    if save_score == SaveScore::Yes {
        let django_fields = scoring_result.to_django_score_fields();
        save_score_with_event(&mut tx, address, scorer_id, passport_id, &django_fields).await?;
    }

    // 11. Process human points if enabled
    let human_points_config = super::human_points::HumanPointsConfig::from_env();
    if human_points_config.enabled && community.human_points_program {
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
    if human_points_config.enabled && community.human_points_program {
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

    Ok((response, scoring_result.timestamp))
}

/// Store a Score row and write its SCORE_UPDATE event (which `/history` returns).
async fn save_score_with_event(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    address: &str,
    scorer_id: i64,
    passport_id: i64,
    fields: &crate::models::django::DjangoScoreFields,
) -> Result<(), DomainError> {
    use crate::models::translation::create_score_update_event_data;

    let score_id = queries::upsert_score(tx, passport_id, fields).await
        .map_err(|e| DomainError::Database(e.to_string()))?;
    let event_data = create_score_update_event_data(
        score_id,
        passport_id,
        fields.score,
        fields.last_score_timestamp,
        fields.evidence.clone(),
        fields.stamp_scores.clone(),
        &fields.stamps,
        fields.expiration_date,
    );
    queries::insert_score_update_event(tx, address, scorer_id, event_data).await
        .map_err(|e| DomainError::Database(e.to_string()))?;
    Ok(())
}

/// Whether a score response may say which wallets are linked.
///
/// Linked wallets are private (internal-docs#3587). Only API keys with
/// `linked_wallet_breakdown` and the internal endpoint get `Show`; every other
/// caller gets `Hide`, which drops `linked_score`. Mirrors Python's
/// `hide_linked_wallets` (`api/v2/api/api_stamps.py`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinkedWallets {
    Show,
    Hide,
}

impl LinkedWallets {
    /// `Show` only for a key that has `linked_wallet_breakdown`.
    pub fn for_api_key(key: &crate::models::django::DjangoApiKey) -> Self {
        if key.linked_wallet_breakdown { Self::Show } else { Self::Hide }
    }
}

/// Drop every field that names another wallet in the address's linked group.
pub fn hide_linked_wallets(mut response: V2ScoreResponse) -> V2ScoreResponse {
    response.linked_score = None;
    for stamp in response.stamps.values_mut() {
        stamp.source_wallet = None;
        stamp.source_wallet_chain_id = None;
    }
    response
}

/// Wallet-group-aware scoring wrapper.
///
/// If the address belongs to a wallet group:
/// - Determines the canonical wallet for this community
/// - Scores all wallets in the group independently
/// - Merges results by provider for the canonical wallet
/// - Persists merged score to the canonical wallet's DB record
/// - Non-canonical wallets get score=0, with linked_score pointing to the
///   canonical when `linked` is `Show`
///
/// If the address is not in a wallet group, delegates to `calculate_score_for_address`.
pub async fn calculate_score_for_address_with_groups(
    address: &str,
    scorer_id: i64,
    pool: &PgPool,
    linked: LinkedWallets,
) -> Result<V2ScoreResponse, DomainError> {
    let wallet = WalletIdentity { address: address.to_lowercase(), chain_id: None };
    match get_wallet_cluster(&wallet).await {
        Ok(Some(cluster)) if cluster.wallets.len() > 1 => {
            let response = score_typed_cluster(pool, scorer_id, &wallet, cluster).await?;
            return Ok(match linked {
                LinkedWallets::Show => response,
                LinkedWallets::Hide => hide_linked_wallets(response),
            });
        }
        Err(error) => tracing::warn!(%error, "Live wallet linkage is unavailable"),
        _ => {}
    }

    // Look up linked-wallet set for this address. Phase 0 uses the solo-only
    // stub in `account::linkage`; Phase 3b will swap the body for a Silk
    // fetch with SWR cache + killswitch + fallback metric.
    let group_addresses = crate::account::linkage::get_linked_addresses(address, pool)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    let response = if group_addresses.len() <= 1 {
        calculate_score_for_address(address, scorer_id, pool).await?
    } else {
        score_wallet_group(address, &group_addresses, scorer_id, pool).await?
    };

    Ok(match linked {
        LinkedWallets::Show => response,
        LinkedWallets::Hide => hide_linked_wallets(response),
    })
}

/// Aggregate current typed membership. The canonical row keeps its individual
/// score so history and later requests cannot retain unlinked contributions.
pub async fn score_typed_cluster(
    pool: &PgPool,
    community_id: i64,
    requester: &WalletIdentity,
    cluster: WalletCluster,
) -> Result<V2ScoreResponse, DomainError> {
    let canonical = cluster.canonical;
    let ordered = std::iter::once(&canonical)
        .chain(cluster.wallets.iter().filter(|wallet| **wallet != canonical));
    let mut responses = HashMap::new();
    let mut stamps = HashMap::new();
    let mut wallet_stamps = HashMap::new();
    let mut legacy_members = Vec::new();
    for wallet in ordered {
        let response = if let Some(chain_id) = wallet.chain_id {
            super::chain_wallet_scoring::score_chain_wallet(pool, community_id, chain_id, &wallet.address)
                .await.map_err(|error| DomainError::Database(error.to_string()))?.score
        } else {
            let save = if *wallet == canonical { SaveScore::Yes } else { SaveScore::No };
            let (response, scored_at) = score_address(&wallet.address, community_id, pool, save).await?;
            if *wallet != canonical {
                legacy_members.push((wallet.address.clone(), scored_at));
            }
            response
        };
        if !response.stamps.is_empty() {
            wallet_stamps.insert(wallet.key(), response.stamps.clone());
        }
        for (provider, stamp) in &response.stamps {
            if !stamp.dedup {
                stamps.entry(provider.clone()).or_insert_with(|| {
                    let mut stamp = stamp.clone();
                    stamp.source_wallet = Some(wallet.address.clone());
                    stamp.source_wallet_chain_id = wallet.chain_id;
                    stamp
                });
            }
        }
        responses.insert(wallet.clone(), response);
    }

    let canonical_score = &responses[&canonical];
    if !legacy_members.is_empty() {
        let mut tx = pool.begin().await.map_err(|error| DomainError::Database(error.to_string()))?;
        for (address, scored_at) in legacy_members {
            let fields = hidden_member_fields(serde_json::json!(canonical_score.threshold), scored_at);
            let passport_id = queries::scoring::upsert_passport_record(&mut tx, &address, community_id)
                .await.map_err(|error| DomainError::Database(error.to_string()))?;
            save_score_with_event(&mut tx, &address, community_id, passport_id, &fields).await?;
        }
        tx.commit().await.map_err(|error| DomainError::Database(error.to_string()))?;
    }

    let raw_score: Decimal = stamps.values().filter_map(|stamp| stamp.score.parse::<Decimal>().ok()).sum();
    let threshold = canonical_score.threshold.parse::<Decimal>()
        .map_err(|error| DomainError::Internal(error.to_string()))?;
    let expiration = stamps.values().filter_map(|stamp| stamp.expiration_date.as_deref())
        .filter_map(|value| DateTime::parse_from_rfc3339(value).ok()).min()
        .map(|value| value.with_timezone(&Utc).to_rfc3339());
    let linked = LinkedScoreResponse {
        address: canonical.address.clone(),
        score: Some(format!("{raw_score:.5}")),
        passing_score: raw_score >= threshold,
        last_score_timestamp: canonical_score.last_score_timestamp.clone(),
        expiration_timestamp: expiration.clone(),
        threshold: canonical_score.threshold.clone(),
        stamps: stamps.clone(),
        wallet_stamps: Some(wallet_stamps),
    };
    let mut response = responses.remove(requester)
        .ok_or_else(|| DomainError::Internal("Requested wallet is missing from the cluster".into()))?;
    if *requester == canonical {
        response.score = linked.score.clone();
        response.passing_score = linked.passing_score;
        response.expiration_timestamp = expiration;
        response.stamps = stamps;
    } else {
        response.score = Some("0.00000".into());
        response.passing_score = false;
        response.expiration_timestamp = None;
        response.stamps.clear();
    }
    response.linked_score = Some(linked);
    Ok(response)
}

/// Score a linked group of two or more wallets. Split out from
/// `calculate_score_for_address_with_groups` so tests can pass the group in
/// while `get_linked_addresses` is still a stub.
async fn score_wallet_group(
    address: &str,
    group_addresses: &[String],
    scorer_id: i64,
    pool: &PgPool,
) -> Result<V2ScoreResponse, DomainError> {
    // Deterministic opaque key for this linked set. Phase 3b will swap this
    // for Silk's user_id so canonical claims survive set membership churn.
    let group_key = build_group_key(group_addresses);

    // Determine canonical wallet (uses transaction for claim write ops)
    let canonical = get_or_set_canonical(pool, &group_key, scorer_id, address).await?;

    // Score all wallets independently. No Score row is saved yet: every save
    // writes a SCORE_UPDATE event, which /history returns. The rows are saved
    // once, after the merge (save_group_scores).
    let mut wallet_responses: HashMap<String, V2ScoreResponse> = HashMap::new();
    // Each wallet's own scoring time: the canonical's for its merged row, and each
    // linked wallet's for its hidden row (sharing the canonical's would pair them).
    let mut wallet_timestamps: HashMap<String, DateTime<Utc>> = HashMap::new();
    for addr in group_addresses {
        let (response, timestamp) = score_address(addr, scorer_id, pool, SaveScore::No).await?;
        wallet_timestamps.insert(addr.clone(), timestamp);
        wallet_responses.insert(addr.clone(), response);
    }
    let canonical_timestamp = *wallet_timestamps.get(&canonical)
        .ok_or_else(|| DomainError::Internal("Canonical wallet is not in the group".into()))?;

    // Canonical first, so its stamps take priority.
    let mut ordered: Vec<&String> = vec![&canonical];
    ordered.extend(group_addresses.iter().filter(|a| **a != canonical));
    let (merged_stamps, combined_raw_score, merged_stamp_scores) =
        merge_group_stamps(&ordered, &wallet_responses);

    // Still need threshold from scorer config
    let scorer_config = queries::load_scorer_config(pool, scorer_id)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?;
    let threshold = scorer_config.threshold;
    let is_passing = combined_raw_score >= threshold;
    let binary_score = if is_passing { Decimal::from(1) } else { Decimal::from(0) };

    // Find earliest expiration from merged stamps (parse to datetime for proper comparison)
    let expiration_dt: Option<chrono::DateTime<Utc>> = merged_stamps.values()
        .filter_map(|s| s.expiration_date.as_deref())
        .filter_map(|s| chrono::DateTime::parse_from_rfc3339(s).ok().map(|dt| dt.with_timezone(&Utc)))
        .min();

    let earliest_expiration: Option<String> = expiration_dt
        .map(|dt| dt.to_rfc3339());

    // Persist the merged score to the canonical wallet's row, and each linked
    // wallet's row in its hidden form, each with its SCORE_UPDATE event.
    let canonical_fields = DjangoScoreFields {
        score: binary_score,
        status: "DONE".to_string(),
        last_score_timestamp: canonical_timestamp,
        expiration_date: expiration_dt,
        error: None,
        evidence: serde_json::json!({
            "type": "ThresholdScoreCheck",
            "success": is_passing,
            "rawScore": format!("{:.5}", combined_raw_score),
            "threshold": format!("{:.5}", threshold),
        }),
        stamp_scores: serde_json::Value::Object(merged_stamp_scores),
        stamps: merged_stamps.iter()
            .map(|(provider, stamp)| (provider.clone(), DjangoStampScore {
                score: stamp.score.clone(),
                dedup: stamp.dedup,
                expiration_date: stamp.expiration_date.clone(),
            }))
            .collect(),
    };
    save_group_scores(pool, scorer_id, &canonical, group_addresses, &canonical_fields, &wallet_timestamps).await?;

    // Build response with merged data
    let canonical_base = wallet_responses.get(&canonical)
        .ok_or_else(|| DomainError::Internal("Canonical response missing".into()))?;

    let score_str = Some(format_decimal_5(combined_raw_score));
    let last_ts = canonical_base.last_score_timestamp.clone();
    let exp_ts = earliest_expiration;
    let threshold_str = format_decimal_5(threshold);

    if address == canonical {
        Ok(V2ScoreResponse {
            address: canonical,
            score: score_str,
            passing_score: is_passing,
            last_score_timestamp: last_ts,
            expiration_timestamp: exp_ts,
            threshold: threshold_str,
            error: None,
            stamps: merged_stamps,
            points_data: None,
            possible_points_data: None,
            linked_score: None,
        })
    } else {
        // Non-canonical: its hidden row as stored (score 0, no stamps, its own
        // scoring time, no expiry), with the group in linked_score.
        let own_ts = wallet_responses.get(address)
            .and_then(|r| r.last_score_timestamp.clone());
        Ok(V2ScoreResponse {
            address: address.to_string(),
            score: Some("0.00000".to_string()),
            passing_score: false,
            last_score_timestamp: own_ts,
            expiration_timestamp: None,
            threshold: threshold_str.clone(),
            error: None,
            stamps: HashMap::new(),
            points_data: None,
            possible_points_data: None,
            linked_score: Some(LinkedScoreResponse {
                address: canonical,
                score: score_str,
                passing_score: is_passing,
                last_score_timestamp: last_ts,
                expiration_timestamp: exp_ts,
                threshold: threshold_str,
                stamps: merged_stamps,
                wallet_stamps: None,
            }),
        })
    }
}

/// Merge a group's stamps by provider: for each provider, the first copy (in
/// `ordered`, canonical first) that was not deduplicated. The group's raw score
/// is the sum of the kept copies' weights, from the per-wallet scoring.
fn merge_group_stamps(
    ordered: &[&String],
    wallet_responses: &HashMap<String, V2ScoreResponse>,
) -> (HashMap<String, V2StampScoreResponse>, Decimal, serde_json::Map<String, serde_json::Value>) {
    let mut merged_stamps: HashMap<String, V2StampScoreResponse> = HashMap::new();
    for addr in ordered {
        if let Some(response) = wallet_responses.get(*addr) {
            for (provider, stamp_data) in &response.stamps {
                if !merged_stamps.contains_key(provider) && !stamp_data.dedup {
                    merged_stamps.insert(provider.clone(), stamp_data.clone());
                }
            }
        }
    }

    let mut combined_raw_score = Decimal::from(0);
    let mut merged_stamp_scores = serde_json::Map::new();
    for (provider, stamp) in &merged_stamps {
        // The weight of the copy that was kept. Looking the provider up wallet by
        // wallet instead can land on another wallet's deduplicated copy (score 0)
        // and drop the stamp's weight from the group.
        let weight = stamp.score.parse::<Decimal>().unwrap_or_default();
        combined_raw_score += weight;
        merged_stamp_scores.insert(
            provider.clone(),
            serde_json::Value::String(format!("{:.5}", weight)),
        );
    }
    (merged_stamps, combined_raw_score, merged_stamp_scores)
}

/// Save a group's Score rows in one transaction: the canonical wallet's merged
/// score, and each linked wallet's row in its hidden form.
async fn save_group_scores(
    pool: &PgPool,
    scorer_id: i64,
    canonical: &str,
    group_addresses: &[String],
    canonical_fields: &DjangoScoreFields,
    wallet_timestamps: &HashMap<String, DateTime<Utc>>,
) -> Result<(), DomainError> {
    let mut tx = pool.begin().await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    let passport_id = queries::scoring::upsert_passport_record(&mut tx, canonical, scorer_id)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?;
    save_score_with_event(&mut tx, canonical, scorer_id, passport_id, canonical_fields).await?;

    for addr in group_addresses.iter().filter(|a| a.as_str() != canonical) {
        let scored_at = *wallet_timestamps.get(addr)
            .ok_or_else(|| DomainError::Internal("Linked wallet was not scored".into()))?;
        let member_fields = hidden_member_score_fields(canonical_fields, scored_at);
        let passport_id = queries::scoring::upsert_passport_record(&mut tx, addr, scorer_id)
            .await
            .map_err(|e| DomainError::Database(e.to_string()))?;
        save_score_with_event(&mut tx, addr, scorer_id, passport_id, &member_fields).await?;
    }

    tx.commit().await
        .map_err(|e| DomainError::Database(e.to_string()))?;
    Ok(())
}

/// A linked (non-canonical) wallet's row, stored as its API response shows it.
///
/// The live response gives the wallet 0 and no stamps. Its own score must not
/// be stored either: the row's SCORE_UPDATE event is what /history returns, so
/// the wallet's own score there would show it is in a group. Mirrors Python's
/// `_save_hidden_member_score` (`api/v2/api/api_stamps.py`).
///
/// `scored_at` is the wallet's own scoring time, and there is no expiry, as for
/// any wallet with no valid stamps: copying the canonical's timestamps would
/// give every wallet in the group identical values, which pairs them.
fn hidden_member_score_fields(
    canonical_fields: &DjangoScoreFields,
    scored_at: DateTime<Utc>,
) -> DjangoScoreFields {
    let threshold = canonical_fields.evidence.get("threshold").cloned()
        .unwrap_or_else(|| serde_json::Value::String("20".to_string()));
    hidden_member_fields(threshold, scored_at)
}

fn hidden_member_fields(
    threshold: serde_json::Value,
    scored_at: DateTime<Utc>,
) -> DjangoScoreFields {
    DjangoScoreFields {
        score: Decimal::from(0),
        status: "DONE".to_string(),
        last_score_timestamp: scored_at,
        expiration_date: None,
        error: None,
        evidence: serde_json::json!({
            "type": "ThresholdScoreCheck",
            "success": false,
            "rawScore": "0",
            "threshold": threshold,
        }),
        stamp_scores: serde_json::json!({}),
        stamps: HashMap::new(),
    }
}

/// Build a deterministic opaque group_key from a linked-wallet set.
/// Phase 3b will replace this with Silk's user_id.
fn build_group_key(addresses: &[String]) -> String {
    let mut sorted: Vec<String> = addresses.iter().map(|a| a.to_lowercase()).collect();
    sorted.sort();
    sorted.join(",")
}

/// Determine or set the canonical wallet for a group+community.
async fn get_or_set_canonical(
    pool: &PgPool,
    group_key: &str,
    scorer_id: i64,
    requesting_address: &str,
) -> Result<String, DomainError> {
    // Check for existing claim
    if let Some(canonical) = queries::wallet_groups::get_canonical_claim(pool, group_key, scorer_id)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?
    {
        // Check if canonical wallet's score is expired
        let score_expired = match queries::scoring::get_score_expiration(pool, &canonical, scorer_id).await {
            Ok(Some(expiration)) => expiration < Utc::now(),
            Ok(None) => false, // No score yet, keep the claim
            Err(_) => false,
        };

        if score_expired {
            // Release the claim within a transaction
            let mut tx = pool.begin().await
                .map_err(|e| DomainError::Database(e.to_string()))?;
            queries::wallet_groups::delete_canonical_claim(&mut tx, group_key, scorer_id)
                .await
                .map_err(|e| DomainError::Database(e.to_string()))?;
            // Set new canonical in same transaction
            let canonical = queries::wallet_groups::upsert_canonical_claim(
                &mut tx, group_key, scorer_id, requesting_address,
            )
            .await
            .map_err(|e| DomainError::Database(e.to_string()))?;
            tx.commit().await
                .map_err(|e| DomainError::Database(e.to_string()))?;
            return Ok(canonical);
        } else {
            return Ok(canonical);
        }
    }

    // No valid claim - requesting address becomes canonical
    let mut tx = pool.begin().await
        .map_err(|e| DomainError::Database(e.to_string()))?;
    let canonical = queries::wallet_groups::upsert_canonical_claim(
        &mut tx, group_key, scorer_id, requesting_address,
    )
    .await
    .map_err(|e| DomainError::Database(e.to_string()))?;
    tx.commit().await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    Ok(canonical)
}

/// Linked-wallet privacy (#977), matching `api/v2/test/test_linked_wallet_privacy.py`.
#[cfg(test)]
mod linked_wallet_privacy_tests {
    use super::*;
    use rust_decimal_macros::dec;
    use serde_json::json;

    fn response_with_linked_score() -> V2ScoreResponse {
        let mut response = V2ScoreResponse::error("0xmember".to_string(), String::new());
        response.error = None;
        response.linked_score = Some(LinkedScoreResponse {
            address: "0xcanonical".to_string(),
            score: Some("25.00000".to_string()),
            passing_score: true,
            last_score_timestamp: None,
            expiration_timestamp: None,
            threshold: "20.00000".to_string(),
            stamps: HashMap::new(),
            wallet_stamps: None,
        });
        response
    }

    #[test]
    fn hide_linked_wallets_drops_the_canonical_wallet() {
        let hidden = hide_linked_wallets(response_with_linked_score());
        assert!(hidden.linked_score.is_none());
        assert!(!serde_json::to_string(&hidden).unwrap().contains("0xcanonical"));
    }

    fn wallet_with(stamps: &[(&str, &str, bool)]) -> V2ScoreResponse {
        V2ScoreResponse {
            address: "0x".to_string(),
            score: None,
            passing_score: false,
            last_score_timestamp: None,
            expiration_timestamp: None,
            threshold: "20.00000".to_string(),
            error: None,
            stamps: stamps.iter().map(|(provider, score, dedup)| (provider.to_string(), V2StampScoreResponse {
                score: score.to_string(),
                dedup: *dedup,
                expiration_date: None,
                source_wallet: None,
                source_wallet_chain_id: None,
            })).collect(),
            points_data: None,
            possible_points_data: None,
            linked_score: None,
        }
    }

    /// The canonical's own copy of Google was deduplicated (score 0); the other
    /// wallet's copy counts. The group gets the counted copy's weight.
    #[test]
    fn merge_uses_the_weight_of_the_copy_it_keeps() {
        let canonical = "0xcanonical".to_string();
        let member = "0xmember".to_string();
        let responses = HashMap::from([
            (canonical.clone(), wallet_with(&[("Google", "0.00000", true), ("Twitter", "15.00000", false)])),
            (member.clone(), wallet_with(&[("Google", "10.00000", false), ("Twitter", "15.00000", false)])),
        ]);

        let (merged, raw, stamp_scores) = merge_group_stamps(&[&canonical, &member], &responses);

        assert_eq!(raw, dec!(25));
        assert_eq!(merged["Google"].score, "10.00000");
        assert!(!merged["Google"].dedup);
        assert_eq!(stamp_scores["Google"], json!("10.00000"));
        assert_eq!(stamp_scores["Twitter"], json!("15.00000"));
    }

    #[test]
    fn hidden_member_row_has_no_score_and_its_own_timestamps() {
        let now = Utc::now();
        let canonical = DjangoScoreFields {
            score: Decimal::from(1),
            status: "DONE".to_string(),
            last_score_timestamp: now,
            expiration_date: Some(now + chrono::Duration::days(30)),
            error: None,
            evidence: json!({"type": "ThresholdScoreCheck", "success": true, "rawScore": "25.00000", "threshold": "20.00000"}),
            stamp_scores: json!({"Google": "25.00000"}),
            stamps: HashMap::from([("Google".to_string(), DjangoStampScore {
                score: "25.00000".to_string(), dedup: false, expiration_date: None,
            })]),
        };
        let scored_at = now + chrono::Duration::milliseconds(40);
        let member = hidden_member_score_fields(&canonical, scored_at);
        assert_eq!(member.score, Decimal::from(0));
        assert_eq!(member.evidence, json!({"type": "ThresholdScoreCheck", "success": false, "rawScore": "0", "threshold": "20.00000"}));
        assert_eq!(member.stamp_scores, json!({}));
        assert!(member.stamps.is_empty());
        assert_eq!(member.last_score_timestamp, scored_at);
        assert_ne!(member.last_score_timestamp, canonical.last_score_timestamp);
        assert_eq!(member.expiration_date, None);
    }

    /// The community's scorer id differs from the community id, as it does in
    /// production after a scorer-type change.
    fn scorer_id_for(community_id: i64) -> i64 {
        community_id + 500
    }

    /// Seed a user, account, scorer and community. Also seeds a decoy scorer whose
    /// id equals the community id, with a different threshold: looking the scorer
    /// up by the community id would load it instead of the community's own.
    async fn seed_community(pool: &PgPool, id: i64) -> sqlx::Result<()> {
        let user_id: i32 = sqlx::query_scalar(
            "INSERT INTO auth_user (password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined)
             VALUES ('', false, $1, '', '', '', false, true, NOW()) RETURNING id",
        ).bind(format!("linked-privacy-{id}")).fetch_one(pool).await?;
        let account_id: i64 = sqlx::query_scalar(
            "INSERT INTO account_account (address, user_id) VALUES ($1, $2) RETURNING id",
        ).bind(format!("0xaccount{id}")).bind(user_id).fetch_one(pool).await?;
        for (scorer_id, threshold) in [(scorer_id_for(id), 20), (id, 99)] {
            sqlx::query("INSERT INTO scorer_weighted_scorer (id, type, exclude_from_weight_updates) VALUES ($1, 'WEIGHTED_BINARY', false)")
                .bind(scorer_id).execute(pool).await?;
            sqlx::query("INSERT INTO scorer_weighted_binaryweightedscorer (scorer_ptr_id, weights, threshold) VALUES ($1, '{}'::jsonb, $2)")
                .bind(scorer_id).bind(threshold).execute(pool).await?;
        }
        sqlx::query(
            "INSERT INTO account_community (id, name, description, account_id, scorer_id, rule, human_points_program)
             VALUES ($1, $2, '', $3, $4, 'LIFO', false)",
        ).bind(id).bind(format!("linked-privacy-{id}")).bind(account_id).bind(scorer_id_for(id)).execute(pool).await?;
        Ok(())
    }

    async fn cleanup(pool: &PgPool, id: i64) {
        for sql in [
            "DELETE FROM registry_event WHERE community_id = $1",
            "DELETE FROM registry_score WHERE passport_id IN (SELECT id FROM registry_passport WHERE community_id = $1)",
            "DELETE FROM registry_hashscorerlink WHERE community_id = $1",
            "DELETE FROM registry_chainwalletscore WHERE community_id = $1",
            "DELETE FROM registry_passport WHERE community_id = $1",
            "DELETE FROM account_walletgroupcommunityclaim WHERE community_id = $1",
            "DELETE FROM account_community WHERE id = $1",
            "DELETE FROM scorer_weighted_binaryweightedscorer WHERE scorer_ptr_id IN ($1, $1 + 500)",
            "DELETE FROM scorer_weighted_scorer WHERE id IN ($1, $1 + 500)",
        ] {
            let _ = sqlx::query(sql).bind(id).execute(pool).await;
        }
        let _ = sqlx::query("DELETE FROM account_account WHERE address = $1").bind(format!("0xaccount{id}")).execute(pool).await;
        let _ = sqlx::query("DELETE FROM auth_user WHERE username = $1").bind(format!("linked-privacy-{id}")).execute(pool).await;
    }

    #[tokio::test]
    async fn external_score_routes_require_scorer_ownership() {
        use axum::{extract::{Path, State}, http::HeaderMap};
        use crate::api::error::ApiError;
        use crate::api::handlers::external::{chain_wallet_score_handler, score_address_handler};
        use crate::auth::api_key::hash_key_sha256;

        let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await.expect("connect");
        let owned_id = 980_000_000 + i64::from(Utc::now().timestamp_subsec_micros());
        let other_id = owned_id + 1_000_000;
        seed_community(&pool, owned_id).await.unwrap();
        seed_community(&pool, other_id).await.unwrap();
        let account_id: i64 = sqlx::query_scalar(
            "SELECT account_id FROM account_community WHERE id = $1",
        )
        .bind(owned_id)
        .fetch_one(&pool)
        .await
        .unwrap();
        let prefix = format!("{owned_id:08x}");
        let key = format!("{prefix}.test-only");
        sqlx::query(
            "INSERT INTO account_accountapikey
                (id, prefix, hashed_key, hashed_key_sha256, created, name, revoked,
                 account_id, create_scorers, read_scores, submit_passports,
                 historical_endpoint, linked_wallet_breakdown)
             VALUES ($1, $1, '', $2, NOW(), 'Ownership test', false, $3, false, true,
                     false, false, true)",
        )
        .bind(&prefix)
        .bind(hash_key_sha256(&key))
        .bind(account_id)
        .execute(&pool)
        .await
        .unwrap();

        let address = format!("0x{owned_id:040x}");
        let mut headers = HeaderMap::new();
        headers.insert("x-api-key", key.parse().unwrap());
        let legacy = score_address_handler(
            Path((other_id, address.clone())), State(pool.clone()), headers.clone(),
        )
        .await;
        let scoped = chain_wallet_score_handler(
            Path((other_id, 8453, address)), State(pool.clone()), headers,
        )
        .await;

        // Clean up before asserting so failing tests don't leave committed fixtures.
        sqlx::query("DELETE FROM account_accountapikeyanalytics WHERE api_key_id = $1")
            .bind(&prefix).execute(&pool).await.unwrap();
        sqlx::query("DELETE FROM account_accountapikey WHERE id = $1")
            .bind(&prefix).execute(&pool).await.unwrap();
        cleanup(&pool, owned_id).await;
        cleanup(&pool, other_id).await;
        assert!(matches!(legacy, Err(ApiError::NotFound(_))));
        assert!(matches!(scoped, Err(ApiError::NotFound(_))));
    }

    #[tokio::test]
    async fn chain_wallet_credential_lookup_and_score_storage_are_scoped() {
        use crate::db::queries::stamps::get_latest_stamps_for_chain;
        use crate::domain::chain_wallet_scoring::score_chain_wallet;
        use crate::domain::dedup::lifo_dedup_for_chain;
        use crate::models::internal::ValidStamp;

        let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await.expect("connect");
        let id = 978_000_000 + i64::from(Utc::now().timestamp_subsec_micros());
        let address = format!("0x{id:040x}");
        cleanup(&pool, id).await;
        seed_community(&pool, id).await.expect("seed scorer");

        let credential = |chain_id, provider, label| json!({
            "credentialSubject": {
                "id": format!("did:pkh:eip155:{chain_id}:{address}"),
                "provider": provider,
            },
            "label": label,
        });
        let base = credential(8453, "Google", "older Base credential");
        let eth = credential(1, "Google", "newer Ethereum credential");
        for (chain_id, provider, stamp, updated) in [
            (8453_i64, "Google", &base, Utc::now() - chrono::Duration::days(1)),
            (1, "Google", &eth, Utc::now()),
            (8453, "Mismatch", &base, Utc::now()),
        ] {
            sqlx::query(
                "INSERT INTO ceramic_cache_chainwalletstamp
                 (chain_id, address, provider, stamp, proof_value, updated_at)
                 VALUES ($1, $2, $3, $4, '', $5)",
            )
            .bind(chain_id)
            .bind(&address)
            .bind(provider)
            .bind(stamp)
            .bind(updated)
            .execute(&pool)
            .await
            .expect("seed credential");
        }
        for (chain_id, expected) in [(8453, base), (1, eth)] {
            assert_eq!(
                get_latest_stamps_for_chain(&pool, &address, chain_id).await.unwrap(),
                vec![expected],
            );
            let score = score_chain_wallet(&pool, id, chain_id, &address).await.unwrap();
            assert_eq!(score.chain_id, chain_id);
        }
        let rows: Vec<(i64, String)> = sqlx::query_as(
            "SELECT chain_id, address FROM registry_chainwalletscore
             WHERE community_id = $1 ORDER BY chain_id",
        )
        .bind(id)
        .fetch_all(&pool)
        .await
        .unwrap();
        assert_eq!(rows, vec![(1, address.clone()), (8453, address.clone())]);

        let stamp = ValidStamp {
            provider: "Google".to_string(),
            credential: json!({}),
            nullifiers: vec!["shared".to_string()],
            expires_at: Utc::now() + chrono::Duration::days(1),
        };
        let mut tx = pool.begin().await.unwrap();
        let first = lifo_dedup_for_chain(
            &[stamp.clone()], &address, 8453, id, &HashMap::new(), &mut tx,
        ).await.unwrap();
        let second = lifo_dedup_for_chain(
            &[stamp], &address, 1, id, &HashMap::new(), &mut tx,
        ).await.unwrap();
        assert_eq!(first.valid_stamps.len(), 1);
        assert!(second.clashing_stamps.contains_key("Google"));
        tx.rollback().await.unwrap();

        // A mainnet smart wallet can already have active, legacy stamps. Its
        // deployed-wallet score reads those stamps until a provider is edited.
        let legacy = credential(1, "Discord", "legacy mainnet credential");
        let revoked = credential(1, "Twitter", "revoked legacy credential");
        for (provider, stamp) in [("Discord", &legacy), ("Twitter", &revoked)] {
            let stamp_id: i64 = sqlx::query_scalar(
                "INSERT INTO ceramic_cache_ceramiccache
                   (type, address, provider, stamp, proof_value, updated_at,
                    compose_db_save_status, compose_db_stream_id)
                 VALUES (1, $1, $2, $3, $2, NOW(), '', '') RETURNING id",
            )
            .bind(&address).bind(provider).bind(stamp).fetch_one(&pool).await.unwrap();
            if provider == "Twitter" {
                sqlx::query(
                    "INSERT INTO ceramic_cache_revocation (proof_value, ceramic_cache_id)
                     VALUES ($1, $2)",
                )
                .bind(provider).bind(stamp_id).execute(&pool).await.unwrap();
            }
        }
        let mainnet = get_latest_stamps_for_chain(&pool, &address, 1).await.unwrap();
        assert_eq!(mainnet[0], legacy);
        assert_eq!(mainnet.len(), 2);
        assert_eq!(get_latest_stamps_for_chain(&pool, &address, 8453).await.unwrap().len(), 1);
        let legacy_reader = queries::stamps::get_latest_stamps_by_provider(&pool, &address)
            .await.unwrap();
        assert_eq!(legacy_reader.len(), 1);
        assert_eq!(legacy_reader[0].stamp, legacy);
        sqlx::query(
            "DELETE FROM ceramic_cache_revocation WHERE ceramic_cache_id IN
             (SELECT id FROM ceramic_cache_ceramiccache WHERE address = $1)",
        )
        .bind(&address).execute(&pool).await.unwrap();
        sqlx::query("DELETE FROM ceramic_cache_ceramiccache WHERE address = $1")
            .bind(&address).execute(&pool).await.unwrap();

        let legacy_rows: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM registry_passport WHERE community_id = $1",
        ).bind(id).fetch_one(&pool).await.unwrap();
        assert_eq!(legacy_rows, 0);
        sqlx::query("DELETE FROM ceramic_cache_chainwalletstamp WHERE address = $1")
            .bind(&address).execute(&pool).await.unwrap();
        cleanup(&pool, id).await;
    }

    async fn stored_score(pool: &PgPool, address: &str, community_id: i64) -> (Decimal, serde_json::Value, serde_json::Value, DateTime<Utc>) {
        sqlx::query_as(
            "SELECT s.score, s.evidence, s.stamps, s.last_score_timestamp FROM registry_score s
             JOIN registry_passport p ON p.id = s.passport_id WHERE p.address = $1 AND p.community_id = $2",
        ).bind(address).bind(community_id).fetch_one(pool).await.expect("score row")
    }

    async fn score_events(pool: &PgPool, address: &str, community_id: i64) -> Vec<serde_json::Value> {
        sqlx::query_scalar("SELECT data FROM registry_event WHERE action = 'SCU' AND address = $1 AND community_id = $2 ORDER BY id")
            .bind(address).bind(community_id).fetch_all(pool).await.expect("events")
    }

    /// A linked wallet's stored row and its SCORE_UPDATE events (what /history
    /// returns) hold the hidden form, never the wallet's own score; the canonical
    /// gets one event per request, holding the merged score.
    #[tokio::test]
    async fn group_scoring_stores_linked_wallets_in_hidden_form() {
        let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await.expect("connect");
        let id = 977_000_000 + (Utc::now().timestamp_subsec_micros() as i64);
        let canonical = format!("0x{:040x}", id);
        let member = format!("0x{:040x}", id + 1);
        cleanup(&pool, id).await;
        seed_community(&pool, id).await.expect("seed");

        // The linked wallet already has its own stored score from before it was linked.
        let mut tx = pool.begin().await.unwrap();
        let member_passport = queries::scoring::upsert_passport_record(&mut tx, &member, id).await.unwrap();
        let old = Utc::now() - chrono::Duration::days(3);
        sqlx::query(
            "INSERT INTO registry_score (passport_id, score, status, last_score_timestamp, evidence, stamps, stamp_scores)
             VALUES ($1, 1, 'DONE', $2, '{\"rawScore\": \"30.00000\"}', '{\"Google\": {}}', '{}')",
        ).bind(member_passport).bind(old).execute(&mut *tx).await.unwrap();
        tx.commit().await.unwrap();

        let group = vec![canonical.clone(), member.clone()];
        let first = score_wallet_group(&canonical, &group, id, &pool).await.expect("score canonical");
        let second = score_wallet_group(&member, &group, id, &pool).await.expect("score member");

        assert_eq!(first.address, canonical);
        assert!(first.linked_score.is_none());
        assert_eq!(second.score.as_deref(), Some("0.00000"));
        assert_eq!(second.linked_score.as_ref().map(|l| l.address.as_str()), Some(canonical.as_str()));

        let (c_score, c_evidence, _, c_ts) = stored_score(&pool, &canonical, id).await;
        let (m_score, m_evidence, m_stamps, m_ts) = stored_score(&pool, &member, id).await;
        assert_eq!(c_score, Decimal::from(0));
        assert_eq!(c_evidence["rawScore"], json!("0.00000"));
        assert_eq!(m_score, Decimal::from(0));
        assert_eq!(m_evidence, json!({"type": "ThresholdScoreCheck", "success": false, "rawScore": "0", "threshold": c_evidence["threshold"]}));
        assert_eq!(m_stamps, json!({}));
        // Identical timestamps would pair the wallets for any caller.
        assert_ne!(m_ts, c_ts, "linked wallet carries its own timestamp, not the canonical's");
        assert_eq!(second.expiration_timestamp, None);
        assert_ne!(second.last_score_timestamp, first.last_score_timestamp);

        let canonical_events = score_events(&pool, &canonical, id).await;
        let member_events = score_events(&pool, &member, id).await;
        assert_eq!(canonical_events.len(), 2, "one SCORE_UPDATE per request, no pre-merge event");
        assert_eq!(member_events.len(), 2);
        for event in &member_events {
            let fields = &event[0]["fields"];
            assert_eq!(fields["score"], json!("0"));
            assert_eq!(fields["evidence"]["rawScore"], json!("0"));
            assert_eq!(fields["stamps"], json!({}));
        }

        cleanup(&pool, id).await;
    }

    /// The scorer comes from `account_community.scorer_id`, not the community id.
    #[tokio::test]
    async fn scorer_config_follows_the_community_scorer() {
        let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await.expect("connect");
        let id = 978_000_000 + (Utc::now().timestamp_subsec_micros() as i64);
        cleanup(&pool, id).await;
        seed_community(&pool, id).await.expect("seed");

        let config = queries::load_scorer_config(&pool, id).await;
        cleanup(&pool, id).await;

        let config = config.expect("scorer config");
        assert_eq!(config.scorer_ptr_id, scorer_id_for(id));
        assert_eq!(config.threshold, Decimal::from(20));
    }
}
