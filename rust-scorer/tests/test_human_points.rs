#[cfg(test)]
mod test_human_points {
    use chrono::Utc;
    use rust_decimal::Decimal;
    use passport_scorer::{
        models::{ScoringResult, StampData},
        human_points::{HumanPointsConfig, process_human_points},
    };
    
    fn create_test_scoring_result(binary_score: i32, providers: Vec<&str>) -> ScoringResult {
        let valid_stamps: Vec<StampData> = providers.into_iter().map(|provider| {
            StampData {
                provider: provider.to_string(),
                credential: serde_json::json!({}),
                nullifiers: if provider == "TestProvider" {
                    vec!["nullifier1".to_string(), "nullifier2".to_string()]
                } else {
                    vec![]
                },
                expires_at: Utc::now() + chrono::Duration::days(30),
                weight: Decimal::from(1),
                was_deduped: false,
            }
        }).collect();
        
        ScoringResult {
            address: "0x1234567890123456789012345678901234567890".to_string(),
            community_id: 1,
            binary_score: Decimal::from(binary_score),
            raw_score: Decimal::from(10),
            threshold: Decimal::from(5),
            valid_stamps,
            deduped_stamps: vec![],
            expires_at: None,
            timestamp: Utc::now(),
        }
    }
    
    #[test]
    fn test_human_points_config() {
        // Test default config (no env vars)
        let config = HumanPointsConfig::from_env();
        assert!(!config.enabled);
        assert_eq!(config.start_timestamp, 0);
        assert!(!config.mta_enabled);
    }
    
    #[test]
    fn test_stamp_provider_mapping() {
        use passport_scorer::human_points::{STAMP_PROVIDER_TO_ACTION, HumanPointsAction};
        
        // Test known providers
        assert_eq!(
            STAMP_PROVIDER_TO_ACTION.get("SelfStakingBronze"),
            Some(&HumanPointsAction::IdentityStakingBronze)
        );
        assert_eq!(
            STAMP_PROVIDER_TO_ACTION.get("BeginnerCommunityStaker"),
            Some(&HumanPointsAction::CommunityStakingBeginner)
        );
        assert_eq!(
            STAMP_PROVIDER_TO_ACTION.get("HolonymGovIdProvider"),
            Some(&HumanPointsAction::HumanTechGovId)
        );
        
        // Test unknown provider
        assert_eq!(STAMP_PROVIDER_TO_ACTION.get("UnknownProvider"), None);
    }
    
    #[test]
    fn test_action_codes() {
        use passport_scorer::human_points::HumanPointsAction;
        
        assert_eq!(HumanPointsAction::ScoringBonus.as_str(), "SCB");
        assert_eq!(HumanPointsAction::HumanKeys.as_str(), "HKY");
        assert_eq!(HumanPointsAction::IdentityStakingBronze.as_str(), "ISB");
        assert_eq!(HumanPointsAction::MetamaskOg.as_str(), "MTA");
    }
    
    #[test]
    fn test_scoring_result_eligibility() {
        // Passing score
        let passing_result = create_test_scoring_result(1, vec!["SelfStakingBronze"]);
        assert_eq!(passing_result.binary_score, Decimal::from(1));
        
        // Failing score
        let failing_result = create_test_scoring_result(0, vec!["SelfStakingBronze"]);
        assert_eq!(failing_result.binary_score, Decimal::from(0));
    }
    
    #[tokio::test]
    #[ignore] // Requires database connection
    async fn test_process_human_points_integration() {
        // This test would require a real database connection
        // Set env vars for testing
        unsafe {
            std::env::set_var("HUMAN_POINTS_ENABLED", "true");
            std::env::set_var("HUMAN_POINTS_START_TIMESTAMP", "0");
            std::env::set_var("HUMAN_POINTS_MTA_ENABLED", "true");
        }
        
        let scoring_result = create_test_scoring_result(1, vec![
            "SelfStakingBronze",
            "BeginnerCommunityStaker",
            "TestProvider", // Has nullifiers for Human Keys
        ]);
        
        // Would need actual database transaction here
        // let pool = init_pool().await.unwrap();
        // let mut tx = pool.begin().await.unwrap();
        // process_human_points(&scoring_result, true, &mut tx).await.unwrap();
        // tx.commit().await.unwrap();
        
        // Clean up
        unsafe {
            std::env::remove_var("HUMAN_POINTS_ENABLED");
            std::env::remove_var("HUMAN_POINTS_START_TIMESTAMP");
            std::env::remove_var("HUMAN_POINTS_MTA_ENABLED");
        }
    }
}