use chrono::Utc;
use rust_decimal::Decimal;
use sqlx::{Postgres, Transaction, PgPool};
use std::collections::HashMap;

use crate::models::{ScoringResult, StampData, PointsData};
use crate::models::human_points::STAMP_PROVIDER_TO_ACTION;
use crate::db::DatabaseError;

/// Configuration for Human Points processing
/// Simple struct to hold env vars
#[derive(Debug, Clone)]
pub struct HumanPointsConfig {
    pub enabled: bool,
    pub write_enabled: bool,
    pub start_timestamp: i64,
    pub mta_enabled: bool,
}

impl HumanPointsConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        Self {
            enabled: std::env::var("HUMAN_POINTS_ENABLED")
                .unwrap_or_else(|_| "false".to_string())
                .parse::<bool>()
                .unwrap_or(false),
            write_enabled: std::env::var("HUMAN_POINTS_WRITE_ENABLED")
                .unwrap_or_else(|_| "false".to_string())
                .parse::<bool>()
                .unwrap_or(false),
            start_timestamp: std::env::var("HUMAN_POINTS_START_TIMESTAMP")
                .unwrap_or_else(|_| "0".to_string())
                .parse::<i64>()
                .unwrap_or(0),
            mta_enabled: std::env::var("HUMAN_POINTS_MTA_ENABLED")
                .unwrap_or_else(|_| "false".to_string())
                .parse::<bool>()
                .unwrap_or(false),
        }
    }
}

/// Process Human Points for a scoring result
/// 
/// This function:
/// 1. Checks if Human Points should be processed (enabled, passing score, etc.)
/// 2. Records passing score for the community
/// 3. Records stamp actions (Human Keys and provider-based actions)
/// 4. Awards scoring bonus if user has 4+ passing communities
/// 5. Awards MetaMask OG bonus if eligible
#[tracing::instrument(skip(scoring_result, tx), fields(address = %scoring_result.address, community_id = scoring_result.community_id))]
pub async fn process_human_points(
    scoring_result: &ScoringResult,
    community_has_program: bool,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    let config = HumanPointsConfig::from_env();
    
    // Check if we should process Human Points
    if !should_process_human_points(&config, scoring_result, community_has_program) {
        return Ok(());
    }
    
    let address = scoring_result.address.to_lowercase();
    let community_id = scoring_result.community_id;
    
    // 1. Record passing score for this community
    record_passing_score(&address, community_id, tx).await?;
    
    // 2. Record stamp actions
    record_stamp_actions(&address, &scoring_result.valid_stamps, tx).await?;
    
    // 3. Check and award scoring bonus (4+ communities)
    check_and_award_scoring_bonus(&address, tx).await?;
    
    // 4. Check and award MetaMask OG bonus if enabled
    if config.mta_enabled {
        check_and_award_metamask_og(&address, tx).await?;
    }

    // 5. Check and award Seasoned Passport OG bonus (no limit)
    check_and_award_seasoned_passport_og(&address, tx).await?;

    // 6. Check and award The Chosen One bonus (no limit)
    check_and_award_the_chosen_one(&address, tx).await?;

    Ok(())
}

/// Check if Human Points should be processed (written)
fn should_process_human_points(
    config: &HumanPointsConfig,
    scoring_result: &ScoringResult,
    community_has_program: bool,
) -> bool {
    // All conditions must be met - uses write_enabled for creating new points
    config.write_enabled
        && community_has_program
        && scoring_result.binary_score == Decimal::from(1)  // Passing score
        && Utc::now().timestamp() >= config.start_timestamp
}

/// Record that an address achieved a passing score in a community
async fn record_passing_score(
    address: &str,
    community_id: i64,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    sqlx::query(
        r#"
        INSERT INTO registry_humanpointscommunityqualifiedusers 
            (address, community_id)
        VALUES ($1, $2)
        ON CONFLICT (address, community_id) DO NOTHING
        "#
    )
    .bind(address)
    .bind(community_id)
    .execute(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;
    
    Ok(())
}

/// Record stamp actions for Human Points
async fn record_stamp_actions(
    address: &str,
    valid_stamps: &[StampData],
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    // First, get all providers that already have Human Keys recorded
    let existing_hky_providers: Vec<String> = sqlx::query_scalar(
        r#"
        SELECT provider 
        FROM registry_humanpoints
        WHERE address = $1 
        AND action = 'HKY'
        AND provider IS NOT NULL
        "#
    )
    .bind(address)
    .fetch_all(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;
    
    let mut addresses = Vec::new();
    let mut actions = Vec::new();
    let mut tx_hashes = Vec::new();
    let mut providers = Vec::new();  // Changed: Use Vec<String> not Vec<Option<String>>
    let mut chain_ids = Vec::new();
    
    for stamp in valid_stamps {
        // Check for Human Keys action (stamps with nullifiers)
        if !stamp.nullifiers.is_empty() && !existing_hky_providers.contains(&stamp.provider) {
            // Use the latest nullifier as tx_hash (matching Python behavior)
            let latest_nullifier = stamp.nullifiers.last()
                .map(|n| n.to_string())
                .unwrap_or_else(|| String::new());
            
            addresses.push(address.to_string());
            actions.push("HKY".to_string());
            tx_hashes.push(latest_nullifier);
            providers.push(stamp.provider.clone());  // Changed: Provider is the stamp provider
            chain_ids.push(0);
        }
        
        // Check for provider-based actions
        if let Some(action) = STAMP_PROVIDER_TO_ACTION.get(stamp.provider.as_str()) {
            addresses.push(address.to_string());
            actions.push(action.as_str().to_string());
            tx_hashes.push(String::new());
            providers.push(String::new());  // Changed: Empty string instead of None
            chain_ids.push(0);
        }
    }
    
    // Bulk insert all actions using UNNEST
    if !addresses.is_empty() {
        sqlx::query(
            r#"
            INSERT INTO registry_humanpoints 
                (address, action, tx_hash, provider, chain_id, timestamp)
            SELECT *, NOW() FROM UNNEST(
                $1::text[], $2::text[], $3::text[], $4::text[], $5::int[]
            )
            ON CONFLICT (address, action, chain_id, provider, tx_hash) DO NOTHING
            "#
        )
        .bind(&addresses)
        .bind(&actions)
        .bind(&tx_hashes)
        .bind(&providers)
        .bind(&chain_ids)
        .execute(&mut **tx)
        .await
        .map_err(DatabaseError::QueryError)?;
    }
    
    Ok(())
}

/// Check and award scoring bonus if user has 4+ passing scores
async fn check_and_award_scoring_bonus(
    address: &str,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    // Count distinct communities where user has passing score
    let passing_count: Option<i32> = sqlx::query_scalar(
        r#"
        SELECT COUNT(DISTINCT community_id)::INT
        FROM registry_humanpointscommunityqualifiedusers
        WHERE address = $1
        "#
    )
    .bind(address)
    .fetch_one(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;
    
    let passing_count = passing_count.unwrap_or(0);
    
    if passing_count >= 4 {
        // Award scoring bonus
        sqlx::query(
            r#"
            INSERT INTO registry_humanpoints 
                (address, action, tx_hash, provider, chain_id, timestamp)
            VALUES ($1, 'SCB', '', '', 0, NOW())
            ON CONFLICT (address, action, chain_id, provider, tx_hash) DO NOTHING
            "#
        )
        .bind(address)
        .execute(&mut **tx)
        .await
        .map_err(DatabaseError::QueryError)?;
    }
    
    Ok(())
}

/// Check and award MetaMask OG bonus if eligible
async fn check_and_award_metamask_og(
    address: &str,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    // Check if address is in MetaMask OG list (simple hardcoded query)
    let is_on_list: Option<bool> = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1
            FROM account_addresslistmember alm
            JOIN account_addresslist al ON alm.list_id = al.id
            WHERE al.name = 'MetaMaskOG'
            AND alm.address = $1
        )
        "#
    )
    .bind(address)
    .fetch_one(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;

    let is_on_list = is_on_list.unwrap_or(false);

    if !is_on_list {
        return Ok(());
    }

    // Check if we've already awarded 5000 MetaMask OG points
    let mta_count: Option<i32> = sqlx::query_scalar(
        r#"
        SELECT COUNT(*)::INT
        FROM registry_humanpoints
        WHERE action = 'MTA'
        "#
    )
    .fetch_one(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;

    let mta_count = mta_count.unwrap_or(0);

    if mta_count < 5000 {
        // Award MetaMask OG points
        sqlx::query(
            r#"
            INSERT INTO registry_humanpoints
                (address, action, tx_hash, provider, chain_id, timestamp)
            VALUES ($1, 'MTA', '', '', 0, NOW())
            ON CONFLICT (address, action, chain_id, provider, tx_hash) DO NOTHING
            "#
        )
        .bind(address)
        .execute(&mut **tx)
        .await
        .map_err(DatabaseError::QueryError)?;
    }

    Ok(())
}

/// Check and award Seasoned Passport OG bonus if eligible (no limit)
async fn check_and_award_seasoned_passport_og(
    address: &str,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    // Check if address is in Seasoned Passport OG list
    let is_on_list: Option<bool> = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1
            FROM account_addresslistmember alm
            JOIN account_addresslist al ON alm.list_id = al.id
            WHERE al.name = 'SeasonedPassportOGs'
            AND alm.address = $1
        )
        "#
    )
    .bind(address)
    .fetch_one(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;

    if is_on_list.unwrap_or(false) {
        // Award Seasoned Passport OG points (no limit check)
        sqlx::query(
            r#"
            INSERT INTO registry_humanpoints
                (address, action, tx_hash, provider, chain_id, timestamp)
            VALUES ($1, 'SOG', '', '', 0, NOW())
            ON CONFLICT (address, action, chain_id, provider, tx_hash) DO NOTHING
            "#
        )
        .bind(address)
        .execute(&mut **tx)
        .await
        .map_err(DatabaseError::QueryError)?;
    }

    Ok(())
}

/// Check and award The Chosen One bonus if eligible (no limit)
async fn check_and_award_the_chosen_one(
    address: &str,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    // Check if address is in The Chosen Ones list
    let is_on_list: Option<bool> = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1
            FROM account_addresslistmember alm
            JOIN account_addresslist al ON alm.list_id = al.id
            WHERE al.name = 'TheChosenOnes'
            AND alm.address = $1
        )
        "#
    )
    .bind(address)
    .fetch_one(&mut **tx)
    .await
    .map_err(DatabaseError::QueryError)?;

    if is_on_list.unwrap_or(false) {
        // Award The Chosen One points (no limit check)
        sqlx::query(
            r#"
            INSERT INTO registry_humanpoints
                (address, action, tx_hash, provider, chain_id, timestamp)
            VALUES ($1, 'TCO', '', '', 0, NOW())
            ON CONFLICT (address, action, chain_id, provider, tx_hash) DO NOTHING
            "#
        )
        .bind(address)
        .execute(&mut **tx)
        .await
        .map_err(DatabaseError::QueryError)?;
    }

    Ok(())
}

/// Get user's Human Points data including total, eligibility, multiplier and breakdown
pub async fn get_user_points_data(
    address: &str,
    pool: &PgPool,
) -> Result<PointsData, DatabaseError> {
    // Query to get points with breakdown (excluding HIM actions)
    let query = r#"
        SELECT
            hp.action,
            hp.chain_id,
            SUM(COALESCE(hpc.points, 0))::INT as action_points
        FROM registry_humanpoints hp
        LEFT JOIN registry_humanpointsconfig hpc
            ON hp.action = hpc.action AND hpc.active = true
        WHERE hp.address = $1
            AND hp.action != 'HIM'
        GROUP BY hp.action, hp.chain_id
    "#;
    
    let rows: Vec<(String, i32, Option<i32>)> = sqlx::query_as(query)
        .bind(address)
        .fetch_all(pool)
        .await
        .map_err(DatabaseError::QueryError)?;
    
    // Get multiplier
    let multiplier: Option<i32> = sqlx::query_scalar(
        "SELECT multiplier FROM registry_humanpointsmultiplier WHERE address = $1"
    )
    .bind(address)
    .fetch_optional(pool)
    .await
    .map_err(DatabaseError::QueryError)?;
    
    let multiplier = multiplier.unwrap_or(1);
    
    // Check eligibility (has passing score in any community)
    let is_eligible: Option<bool> = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM registry_humanpointscommunityqualifiedusers
            WHERE address = $1
        )
        "#
    )
    .bind(address)
    .fetch_one(pool)
    .await
    .map_err(DatabaseError::QueryError)?;
    
    let is_eligible = is_eligible.unwrap_or(false);
    
    // Build breakdown
    let mut breakdown = HashMap::new();
    let mut total_points = 0;
    
    for (action, chain_id, points) in rows {
        let points = points.unwrap_or(0);
        total_points += points;
        
        // Add chain-specific breakdown if chain_id is not 0
        if chain_id != 0 {
            let key = format!("{}_{}", action, chain_id);
            breakdown.insert(key, points);
        }
        
        // Add or accumulate to action total
        breakdown.entry(action.clone())
            .and_modify(|e| *e += points)
            .or_insert(points);
    }
    
    Ok(PointsData {
        total_points,
        is_eligible,
        multiplier,  // Already an i32
        breakdown,   // Already a HashMap<String, i32>
    })
}

/// Get possible points data (all available points with current multiplier)
pub async fn get_possible_points_data(
    multiplier: i32,
    pool: &PgPool,
) -> Result<PointsData, DatabaseError> {
    // Get all active point configurations
    let configs: Vec<(String, i32)> = sqlx::query_as(
        "SELECT action, points FROM registry_humanpointsconfig WHERE active = true"
    )
    .fetch_all(pool)
    .await
    .map_err(DatabaseError::QueryError)?;
    
    let mut breakdown = HashMap::new();
    
    for (action, points) in configs {
        // Include all actions in breakdown, including HIM
        breakdown.insert(action, points);
    }
    
    // NOTE: Django returns total_points: 0 for possible_points_data even though
    // the breakdown values sum to more. This reuses the PointsData struct in a way
    // that should probably be refactored to use separate types for user vs possible points.
    Ok(PointsData {
        total_points: 0,  // Matches Django behavior
        is_eligible: false,  // Not applicable for possible points
        multiplier,
        breakdown,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use rust_decimal::Decimal;
    
    #[test]
    fn test_config_from_env() {
        // Test with no env vars set
        let config = HumanPointsConfig::from_env();
        assert!(!config.enabled);
        assert_eq!(config.start_timestamp, 0);
        assert!(!config.mta_enabled);
        
        // Test with env vars set
        unsafe {
            std::env::set_var("HUMAN_POINTS_ENABLED", "true");
            std::env::set_var("HUMAN_POINTS_START_TIMESTAMP", "1234567890");
            std::env::set_var("HUMAN_POINTS_MTA_ENABLED", "true");
        }
        
        let config = HumanPointsConfig::from_env();
        assert!(config.enabled);
        assert_eq!(config.start_timestamp, 1234567890);
        assert!(config.mta_enabled);
        
        // Clean up
        unsafe {
            std::env::remove_var("HUMAN_POINTS_ENABLED");
            std::env::remove_var("HUMAN_POINTS_START_TIMESTAMP");
            std::env::remove_var("HUMAN_POINTS_MTA_ENABLED");
        }
    }
    
    #[test]
    fn test_should_process_human_points() {
        let config = HumanPointsConfig {
            enabled: true,
            write_enabled: true,
            start_timestamp: 1000,
            mta_enabled: false,
        };
        
        let mut scoring_result = ScoringResult {
            address: "0x123".to_string(),
            community_id: 1,
            binary_score: Decimal::from(1),
            raw_score: Decimal::from(10),
            threshold: Decimal::from(5),
            valid_stamps: vec![],
            deduped_stamps: vec![],
            expires_at: None,
            timestamp: Utc::now(),
        };
        
        // All conditions met
        assert!(should_process_human_points(&config, &scoring_result, true));
        
        // Not passing score
        scoring_result.binary_score = Decimal::from(0);
        assert!(!should_process_human_points(&config, &scoring_result, true));
        
        // Community doesn't have program
        scoring_result.binary_score = Decimal::from(1);
        assert!(!should_process_human_points(&config, &scoring_result, false));
        
        // Write not enabled
        let disabled_config = HumanPointsConfig {
            enabled: true,
            write_enabled: false,
            start_timestamp: 1000,
            mta_enabled: false,
        };
        assert!(!should_process_human_points(&disabled_config, &scoring_result, true));
    }
}
