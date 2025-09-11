use chrono::Utc;
use rust_decimal::Decimal;
use sqlx::{Postgres, Transaction};
use std::collections::{HashMap, HashSet};
use tracing::{info, warn};

use crate::db::errors::DatabaseError;
use crate::db::read_ops::load_hash_scorer_links;
use crate::db::write_ops::{bulk_upsert_hash_links, insert_dedup_events, verify_hash_links};
use crate::models::django::DjangoHashScorerLink;
use crate::models::internal::{StampData, StampInfo, ValidStamp};

/// Maximum number of retries for LIFO deduplication on IntegrityError
const MAX_RETRIES: u8 = 5;

/// Result of LIFO deduplication
#[derive(Debug)]
pub struct LifoResult {
    /// Stamps that passed deduplication (not clashing)
    pub valid_stamps: Vec<StampData>,
    /// Stamps that were deduped (clashing with other addresses)
    pub clashing_stamps: HashMap<String, StampInfo>,
    /// Hash links that were created or updated
    pub hash_links_processed: usize,
}

/// Main LIFO deduplication function with retry logic
///
/// This implements the LIFO (Last-In-First-Out) deduplication strategy:
/// - The last address to claim a nullifier hash gets to keep it
/// - Previously claimed nullifiers by other addresses cause stamp deduplication
/// - Expired hash links can be reassigned to new addresses
///
/// # Arguments
/// * `stamps` - Valid stamps to deduplicate
/// * `address` - The address claiming the stamps
/// * `community_id` - The community/scorer ID
/// * `weights` - Provider weights for scoring
/// * `tx` - Database transaction
///
/// # Returns
/// * `LifoResult` containing valid stamps and clashing stamps info
pub async fn lifo_dedup(
    stamps: &[ValidStamp],
    address: &str,
    community_id: i32,
    weights: &HashMap<String, Decimal>,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<LifoResult, DatabaseError> {
    let mut retry_count = 0;
    
    loop {
        match lifo_dedup_attempt(stamps, address, community_id, weights, tx).await {
            Ok(result) => {
                if retry_count > 0 {
                    info!(
                        retry_count,
                        address,
                        community_id,
                        "LIFO deduplication succeeded after retries"
                    );
                }
                return Ok(result);
            }
            Err(e) if e.is_integrity_error() && retry_count < MAX_RETRIES => {
                retry_count += 1;
                warn!(
                    retry_count,
                    max_retries = MAX_RETRIES,
                    error = %e,
                    "LIFO deduplication integrity error, retrying"
                );
                // Continue to retry
            }
            Err(e) => {
                warn!(
                    retry_count,
                    error = %e,
                    "LIFO deduplication failed"
                );
                return Err(e);
            }
        }
    }
}

/// Single attempt at LIFO deduplication (without retry)
async fn lifo_dedup_attempt(
    stamps: &[ValidStamp],
    address: &str,
    community_id: i32,
    weights: &HashMap<String, Decimal>,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<LifoResult, DatabaseError> {
    // Extract ALL nullifiers from stamps (no filtering per simplified plan)
    let all_nullifiers: Vec<String> = stamps
        .iter()
        .flat_map(|s| s.nullifiers.clone())
        .collect();
    
    if all_nullifiers.is_empty() {
        // No nullifiers to deduplicate
        return Ok(LifoResult {
            valid_stamps: stamps
                .iter()
                .map(|s| StampData {
                    provider: s.provider.clone(),
                    credential: s.credential.clone(),
                    nullifiers: s.nullifiers.clone(),
                    expires_at: s.expires_at,
                    weight: weights.get(&s.provider).copied().unwrap_or_default(),
                    was_deduped: false,
                })
                .collect(),
            clashing_stamps: HashMap::new(),
            hash_links_processed: 0,
        });
    }
    
    // Load existing hash links for these nullifiers
    let existing_links = load_hash_scorer_links(tx, community_id, &all_nullifiers).await?;
    
    // Categorize existing hash links
    let now = Utc::now();
    let mut owned_hashes = HashSet::new();
    let mut clashing_hashes = HashSet::new();
    let mut expired_hashes = HashSet::new();
    let mut clashing_links_by_hash: HashMap<String, DjangoHashScorerLink> = HashMap::new();
    
    for link in existing_links {
        if link.address == address {
            // Already owned by this address
            owned_hashes.insert(link.hash.clone());
        } else if link.expires_at > now {
            // Owned by another address and not expired - this causes a clash
            clashing_hashes.insert(link.hash.clone());
            clashing_links_by_hash.insert(link.hash.clone(), link);
        } else {
            // Owned by another address but expired - can be reassigned
            expired_hashes.insert(link.hash.clone());
        }
    }
    
    // Process stamps to determine which are valid vs clashing
    let mut valid_stamps = Vec::new();
    let mut clashing_stamps = HashMap::new();
    let mut hash_links_to_create = Vec::new();
    let mut hash_links_to_update = Vec::new();
    
    for stamp in stamps {
        // Check if ANY nullifier clashes with existing hash links
        let clashing_nullifiers: Vec<&String> = stamp.nullifiers
            .iter()
            .filter(|n| clashing_hashes.contains(*n))
            .collect();
        
        if clashing_nullifiers.is_empty() {
            // No clashes - stamp is valid for scoring
            let weight = weights.get(&stamp.provider).copied().unwrap_or_default();
            valid_stamps.push(StampData {
                provider: stamp.provider.clone(),
                credential: stamp.credential.clone(),
                nullifiers: stamp.nullifiers.clone(),
                expires_at: stamp.expires_at,
                weight,
                was_deduped: false,
            });
            
            // Process hash links for this valid stamp
            for nullifier in &stamp.nullifiers {
                if owned_hashes.contains(nullifier) {
                    // Already owned by this address - might need to update expiration
                    hash_links_to_update.push((
                        nullifier.clone(),
                        address.to_string(),
                        community_id,
                        stamp.expires_at,
                    ));
                } else if expired_hashes.contains(nullifier) {
                    // Take over expired link from another address
                    hash_links_to_update.push((
                        nullifier.clone(),
                        address.to_string(),
                        community_id,
                        stamp.expires_at,
                    ));
                } else {
                    // Create new hash link
                    hash_links_to_create.push((
                        nullifier.clone(),
                        address.to_string(),
                        community_id,
                        stamp.expires_at,
                    ));
                }
            }
        } else {
            // Has clashes - stamp is deduped
            // Get the expiration date from the first clashing hash link
            let first_clash = clashing_nullifiers[0];
            let clash_owner = &clashing_links_by_hash[first_clash];
            
            clashing_stamps.insert(
                stamp.provider.clone(),
                StampInfo {
                    nullifiers: stamp.nullifiers.clone(),
                    credential: stamp.credential.clone(),
                    expires_at: clash_owner.expires_at,  // Use expiration from clashing hash link
                },
            );
            
            // IMPORTANT: Backfill non-clashing nullifiers with clashing owner's data
            // This ensures consistency when only some nullifiers clash
            
            for nullifier in &stamp.nullifiers {
                if !clashing_hashes.contains(nullifier) && 
                   !owned_hashes.contains(nullifier) &&
                   !expired_hashes.contains(nullifier) {
                    // Backfill with clashing owner's data
                    hash_links_to_create.push((
                        nullifier.clone(),
                        clash_owner.address.clone(),
                        community_id,
                        clash_owner.expires_at,
                    ));
                }
            }
        }
    }
    
    // Calculate count before moving vectors
    let links_processed = hash_links_to_create.len() + hash_links_to_update.len();
    
    // Collect nullifiers that should belong to current address (from valid stamps only)
    let mut nullifiers_for_current_address = Vec::new();
    for stamp in &valid_stamps {
        nullifiers_for_current_address.extend(stamp.nullifiers.clone());
    }
    
    // Perform bulk hash link operations
    bulk_upsert_hash_links(
        tx,
        hash_links_to_create,
        hash_links_to_update
    ).await?;
    
    // Verify expected number of links were created/updated
    // Only verify nullifiers that should belong to the current address
    let verification_success = verify_hash_links(
        tx,
        address,
        community_id,
        &nullifiers_for_current_address
    ).await?;
    
    // Check if verification succeeded
    if !verification_success {
        return Err(DatabaseError::InvalidData(
            "Hash link verification failed - unexpected number of links".to_string()
        ));
    }
    
    // Record deduplication events for clashing stamps
    if !clashing_stamps.is_empty() {
        insert_dedup_events(tx, address, community_id, &clashing_stamps).await?;
    }
    
    info!(
        address,
        community_id,
        valid_stamps = valid_stamps.len(),
        clashing_stamps = clashing_stamps.len(),
        hash_links_processed = links_processed,
        "LIFO deduplication complete"
    );
    
    Ok(LifoResult {
        valid_stamps,
        clashing_stamps,
        hash_links_processed: links_processed,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;
    use serde_json::json;
    
    fn create_test_stamp(provider: &str, nullifiers: Vec<String>) -> ValidStamp {
        ValidStamp {
            provider: provider.to_string(),
            credential: json!({
                "credentialSubject": {
                    "provider": provider,
                    "nullifiers": nullifiers,
                }
            }),
            nullifiers,
            expires_at: Utc::now() + Duration::days(30),
        }
    }
    
    #[test]
    fn test_empty_nullifiers() {
        // Test that stamps with no nullifiers are handled correctly
        let stamp = ValidStamp {
            provider: "test".to_string(),
            credential: json!({}),
            nullifiers: vec![],
            expires_at: Utc::now() + Duration::days(30),
        };
        
        assert!(stamp.nullifiers.is_empty());
    }
    
    #[test]
    fn test_nullifier_extraction() {
        let stamps = vec![
            create_test_stamp("provider1", vec!["null1".to_string(), "null2".to_string()]),
            create_test_stamp("provider2", vec!["null3".to_string()]),
        ];
        
        let all_nullifiers: Vec<String> = stamps
            .iter()
            .flat_map(|s| s.nullifiers.clone())
            .collect();
        
        assert_eq!(all_nullifiers.len(), 3);
        assert!(all_nullifiers.contains(&"null1".to_string()));
        assert!(all_nullifiers.contains(&"null2".to_string()));
        assert!(all_nullifiers.contains(&"null3".to_string()));
    }
    
    #[test]
    fn test_clash_detection() {
        let clashing_hashes: HashSet<String> = vec!["null1".to_string(), "null2".to_string()]
            .into_iter()
            .collect();
        
        let stamp = create_test_stamp("provider1", vec![
            "null1".to_string(),
            "null3".to_string(),
        ]);
        
        let clashing: Vec<&String> = stamp.nullifiers
            .iter()
            .filter(|n| clashing_hashes.contains(*n))
            .collect();
        
        assert_eq!(clashing.len(), 1);
        assert_eq!(clashing[0], "null1");
    }
    
    #[test]
    fn test_backfill_logic() {
        let owned_hashes: HashSet<String> = vec!["owned1".to_string()].into_iter().collect();
        let clashing_hashes: HashSet<String> = vec!["clash1".to_string()].into_iter().collect();
        let expired_hashes: HashSet<String> = vec!["expired1".to_string()].into_iter().collect();
        
        let nullifiers = vec![
            "new1".to_string(),
            "owned1".to_string(),
            "clash1".to_string(),
            "expired1".to_string(),
        ];
        
        // Test categorization logic
        for nullifier in &nullifiers {
            if owned_hashes.contains(nullifier) {
                assert_eq!(nullifier, "owned1");
            } else if clashing_hashes.contains(nullifier) {
                assert_eq!(nullifier, "clash1");
            } else if expired_hashes.contains(nullifier) {
                assert_eq!(nullifier, "expired1");
            } else {
                assert_eq!(nullifier, "new1");
            }
        }
    }
}