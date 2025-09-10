#[cfg(test)]
mod tests {
    use super::super::*;
    use chrono::{TimeZone, Utc};
    
    use rust_decimal_macros::dec;
    use serde_json::json;
    use std::collections::HashMap;
    use pretty_assertions::assert_eq;

    fn create_test_scoring_result() -> ScoringResult {
        let timestamp = Utc.with_ymd_and_hms(2024, 1, 15, 12, 0, 0).unwrap();
        let expires_at = Utc.with_ymd_and_hms(2024, 12, 31, 23, 59, 59).unwrap();
        
        let valid_stamps = vec![
            StampData {
                provider: "Google".to_string(),
                credential: json!({
                    "credentialSubject": {
                        "provider": "Google",
                        "id": "did:pkh:eip155:1:0x1234567890abcdef",
                        "nullifiers": ["v0-google-123"]
                    },
                    "expirationDate": expires_at.to_rfc3339()
                }),
                nullifiers: vec!["v0-google-123".to_string()],
                expires_at,
                weight: dec!(10.5),
                was_deduped: false,
            },
            StampData {
                provider: "Twitter".to_string(),
                credential: json!({
                    "credentialSubject": {
                        "provider": "Twitter",
                        "id": "did:pkh:eip155:1:0x1234567890abcdef",
                        "nullifiers": ["v0-twitter-456"]
                    },
                    "expirationDate": expires_at.to_rfc3339()
                }),
                nullifiers: vec!["v0-twitter-456".to_string()],
                expires_at,
                weight: dec!(5.25),
                was_deduped: false,
            },
        ];
        
        let deduped_stamps = vec![
            StampData {
                provider: "Discord".to_string(),
                credential: json!({
                    "credentialSubject": {
                        "provider": "Discord",
                        "id": "did:pkh:eip155:1:0x1234567890abcdef",
                        "nullifiers": ["v0-discord-789"]
                    },
                    "expirationDate": expires_at.to_rfc3339()
                }),
                nullifiers: vec!["v0-discord-789".to_string()],
                expires_at,
                weight: dec!(0),
                was_deduped: true,
            },
        ];
        
        ScoringResult {
            address: "0x1234567890abcdef".to_string(),
            community_id: 42,
            binary_score: dec!(1),
            raw_score: dec!(15.75),
            threshold: dec!(15),
            valid_stamps,
            deduped_stamps,
            expires_at: Some(expires_at),
            timestamp,
        }
    }

    #[test]
    fn test_to_v2_response() {
        let result = create_test_scoring_result();
        let response = result.to_v2_response();
        
        assert_eq!(response.address, "0x1234567890abcdef");
        assert_eq!(response.score, Some("1.00000".to_string()));
        assert_eq!(response.passing_score, true);
        assert_eq!(response.threshold, "15.00000");
        assert!(response.last_score_timestamp.is_some());
        assert!(response.expiration_timestamp.is_some());
        assert_eq!(response.error, None);
        
        // Check stamps
        assert_eq!(response.stamps.len(), 3);
        
        // Valid stamps should have their weights as scores
        let google_stamp = response.stamps.get("Google").unwrap();
        assert_eq!(google_stamp.score, "10.50000");
        assert_eq!(google_stamp.dedup, false);
        
        let twitter_stamp = response.stamps.get("Twitter").unwrap();
        assert_eq!(twitter_stamp.score, "5.25000");
        assert_eq!(twitter_stamp.dedup, false);
        
        // Deduped stamps should have zero score
        let discord_stamp = response.stamps.get("Discord").unwrap();
        assert_eq!(discord_stamp.score, "0.00000");
        assert_eq!(discord_stamp.dedup, true);
    }

    #[test]
    fn test_to_django_score_fields() {
        let result = create_test_scoring_result();
        let django_fields = result.to_django_score_fields();
        
        assert_eq!(django_fields.score, dec!(1));
        assert_eq!(django_fields.status, "DONE");
        assert_eq!(django_fields.error, None);
        
        // Check evidence structure
        let evidence = django_fields.evidence;
        assert_eq!(evidence["type"], "ThresholdScoreCheck");
        assert_eq!(evidence["success"], true);
        assert_eq!(evidence["rawScore"], "15.75");
        assert_eq!(evidence["threshold"], "15");
        
        // Check stamp_scores (should only have valid stamps)
        let stamp_scores = django_fields.stamp_scores.as_object().unwrap();
        assert_eq!(stamp_scores.len(), 2);
        assert!(stamp_scores.contains_key("Google"));
        assert!(stamp_scores.contains_key("Twitter"));
        assert!(!stamp_scores.contains_key("Discord"));
        
        // Check stamps dict (should have all stamps)
        assert_eq!(django_fields.stamps.len(), 3);
        assert!(django_fields.stamps.contains_key("Google"));
        assert!(django_fields.stamps.contains_key("Twitter"));
        assert!(django_fields.stamps.contains_key("Discord"));
    }

    #[test]
    fn test_binary_score_calculation() {
        let mut result = create_test_scoring_result();
        
        // Test passing score
        result.raw_score = dec!(20);
        result.threshold = dec!(15);
        result.binary_score = if result.raw_score >= result.threshold {
            dec!(1)
        } else {
            dec!(0)
        };
        assert_eq!(result.binary_score, dec!(1));
        
        // Test failing score
        result.raw_score = dec!(10);
        result.threshold = dec!(15);
        result.binary_score = if result.raw_score >= result.threshold {
            dec!(1)
        } else {
            dec!(0)
        };
        assert_eq!(result.binary_score, dec!(0));
        
        // Test exact threshold
        result.raw_score = dec!(15);
        result.threshold = dec!(15);
        result.binary_score = if result.raw_score >= result.threshold {
            dec!(1)
        } else {
            dec!(0)
        };
        assert_eq!(result.binary_score, dec!(1));
    }

    #[test]
    fn test_to_scoring_event() {
        let result = create_test_scoring_result();
        let event = result.to_scoring_event();
        
        assert_eq!(event.address, "0x1234567890abcdef");
        assert_eq!(event.community_id, 42);
        assert_eq!(event.score, dec!(1));
        assert_eq!(event.threshold, dec!(15));
        assert_eq!(event.raw_score, dec!(15.75));
        
        // Check weights
        assert_eq!(event.weights.len(), 2);
        assert_eq!(event.weights.get("Google"), Some(&dec!(10.5)));
        assert_eq!(event.weights.get("Twitter"), Some(&dec!(5.25)));
        
        // Check stamps snapshot
        let valid = event.stamps_snapshot["valid"].as_array().unwrap();
        let deduped = event.stamps_snapshot["deduped"].as_array().unwrap();
        assert_eq!(valid.len(), 2);
        assert_eq!(deduped.len(), 1);
    }

    #[test]
    fn test_score_update_event_data() {
        use super::super::translation::create_score_update_event_data;
        
        let timestamp = Utc::now();
        let expires_at = Utc.with_ymd_and_hms(2024, 12, 31, 23, 59, 59).unwrap();
        
        let mut stamps = HashMap::new();
        stamps.insert(
            "Google".to_string(),
            DjangoStampScore {
                score: "10.50000".to_string(),
                dedup: false,
                expiration_date: Some(expires_at.to_rfc3339()),
            },
        );
        
        let event_data = create_score_update_event_data(
            123,  // score_id
            456,  // passport_id
            dec!(1),
            timestamp,
            json!({
                "type": "ThresholdScoreCheck",
                "success": true,
                "rawScore": "15.75",
                "threshold": "15"
            }),
            json!({"Google": 10.5}),
            &stamps,
            Some(expires_at),
        );
        
        // Check it's an array with one element
        let array = event_data.as_array().unwrap();
        assert_eq!(array.len(), 1);
        
        let event = &array[0];
        assert_eq!(event["model"], "registry.score");
        assert_eq!(event["pk"], 123);
        
        let fields = &event["fields"];
        assert_eq!(fields["passport"], 456);
        assert_eq!(fields["score"], "1");
        assert_eq!(fields["status"], "DONE");
        assert_eq!(fields["error"], json!(null));
        assert!(fields["last_score_timestamp"].is_string());
        assert!(fields["evidence"].is_object());
        assert!(fields["stamp_scores"].is_object());
        assert!(fields["stamps"].is_object());
        assert!(fields["expiration_date"].is_string());
    }

    #[test]
    fn test_v2_error_response() {
        let error_response = V2ScoreResponse::error(
            "0xabc123".to_string(),
            "Invalid credentials".to_string(),
        );
        
        assert_eq!(error_response.address, "0xabc123");
        assert_eq!(error_response.score, None);
        assert_eq!(error_response.passing_score, false);
        assert_eq!(error_response.threshold, "0.00000");
        assert_eq!(error_response.error, Some("Invalid credentials".to_string()));
        assert!(error_response.stamps.is_empty());
        assert_eq!(error_response.last_score_timestamp, None);
        assert_eq!(error_response.expiration_timestamp, None);
    }

    #[test]
    fn test_decimal_formatting() {
        use super::super::v2_api::format_decimal_5;
        
        assert_eq!(format_decimal_5(dec!(1)), "1.00000");
        assert_eq!(format_decimal_5(dec!(10.5)), "10.50000");
        assert_eq!(format_decimal_5(dec!(0.12345)), "0.12345");
        assert_eq!(format_decimal_5(dec!(99.999999)), "99.99999");
        assert_eq!(format_decimal_5(dec!(0)), "0.00000");
    }
}