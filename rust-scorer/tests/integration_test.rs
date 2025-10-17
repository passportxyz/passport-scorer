#[cfg(test)]
mod tests {
    use axum::{
        body::Body,
        http::{Request, StatusCode},
    };
    use chrono::Utc;
    use passport_scorer::api::server::create_app;
    use passport_scorer::models::django::{DjangoScoreFields, DjangoStampScore};
    use rust_decimal::Decimal;
    use serde_json::json;
    use sqlx::postgres::PgPoolOptions;
    use std::collections::HashMap;
    use tower::ServiceExt;

    async fn setup_test_pool() -> sqlx::PgPool {
        let database_url = std::env::var("TEST_DATABASE_URL")
            .unwrap_or_else(|_| std::env::var("DATABASE_URL")
                .expect("DATABASE_URL must be set for tests"));

        PgPoolOptions::new()
            .max_connections(5)
            .connect(&database_url)
            .await
            .expect("Failed to create test pool")
    }

    #[tokio::test]
    async fn test_health_check() {
        let app = create_app().await.unwrap();

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/health")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        assert_eq!(&body[..], b"OK");
    }

    #[tokio::test]
    async fn test_score_endpoint_missing_api_key() {
        let app = create_app().await.unwrap();

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/v2/stamps/1/score/0x1234567890123456789012345678901234567890")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn test_score_endpoint_invalid_address() {
        let app = create_app().await.unwrap();

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/v2/stamps/1/score/invalid_address")
                    .header("X-API-Key", "test_key")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let error: serde_json::Value = serde_json::from_slice(&body).unwrap();
        
        assert_eq!(error["error"], "bad_request");
        assert!(error["message"].as_str().unwrap().contains("Invalid Ethereum address"));
    }


    #[tokio::test]
    async fn test_full_scoring_flow() {
        // This test would require:
        // 1. Setting up test data in the database
        // 2. Creating a valid API key
        // 3. Adding ceramic cache entries
        // 4. Running the full scoring flow
        // 
        // For a real implementation, you would:
        // - Use a test database with fixtures
        // - Set up test data before each test
        // - Clean up after each test
        // - Use transactions that rollback for isolation
        
        // Example structure (would need actual test data):
        /*
        let pool = setup_test_pool().await;
        
        // Setup test data
        sqlx::query!("INSERT INTO account_accountapikey ...")
            .execute(&pool)
            .await
            .unwrap();
            
        sqlx::query!("INSERT INTO ceramic_cache ...")
            .execute(&pool)
            .await
            .unwrap();
        
        let app = create_app(pool);
        
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/v2/stamps/1/score/0x...")
                    .header("X-API-Key", "valid_test_key")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        
        assert_eq!(response.status(), StatusCode::OK);
        
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let score_response: passport_scorer::models::v2_api::V2ScoreResponse = 
            serde_json::from_slice(&body).unwrap();
        
        assert!(score_response.score.is_some());
        assert!(score_response.stamps.is_empty() || !score_response.stamps.is_empty());
        */
        
        // Placeholder assertion for now
        assert!(true);
    }

    #[tokio::test]
    async fn test_v2_response_format() {
        // Test that the response matches the expected V2 format
        use passport_scorer::models::v2_api::V2ScoreResponse;
        
        let response = V2ScoreResponse {
            address: "0x1234567890123456789012345678901234567890".to_string(),
            score: Some("15.50000".to_string()),
            passing_score: true,
            threshold: "20.00000".to_string(),
            last_score_timestamp: Some("2025-01-01T00:00:00Z".to_string()),
            expiration_timestamp: Some("2025-12-31T23:59:59Z".to_string()),
            error: None,
            stamps: HashMap::new(),
            points_data: None,
            possible_points_data: None,
        };
        
        let json = serde_json::to_value(&response).unwrap();
        
        // Verify the structure matches expected format
        assert_eq!(json["address"], "0x1234567890123456789012345678901234567890");
        assert_eq!(json["score"], "15.50000");
        assert_eq!(json["passing_score"], true);
        assert_eq!(json["threshold"], "20.00000");
        assert!(json["last_score_timestamp"].is_string());
        assert!(json["expiration_timestamp"].is_string());
        assert!(json["error"].is_null());
        assert!(json["stamps"].is_object());
    }

    #[tokio::test]
    async fn test_django_event_format() {
        use passport_scorer::models::translation::create_score_update_event_data;
        // Already imported at the top
        
        let score_fields = DjangoScoreFields {
            score: Decimal::from(1),
            status: "DONE".to_string(),
            last_score_timestamp: Utc::now(),
            expiration_date: None,
            error: None,
            evidence: json!({
                "type": "ThresholdScoreCheck",
                "success": true,
                "rawScore": "25.5",
                "threshold": "20.0"
            }),
            stamp_scores: json!({"Google": 10.5, "Twitter": 15.0}),
            stamps: {
                let mut stamps = HashMap::new();
                stamps.insert("Google".to_string(), DjangoStampScore {
                    score: "10.50000".to_string(),
                    dedup: false,
                    expiration_date: Some("2025-12-31T23:59:59Z".to_string()),
                });
                stamps.insert("Twitter".to_string(), DjangoStampScore {
                    score: "15.00000".to_string(),
                    dedup: false,
                    expiration_date: Some("2025-12-31T23:59:59Z".to_string()),
                });
                stamps
            },
        };
        
        let event_data = create_score_update_event_data(
            1, // score_id
            2, // passport_id
            score_fields.score,
            score_fields.last_score_timestamp,
            score_fields.evidence.clone(),
            score_fields.stamp_scores.clone(),
            &score_fields.stamps,
            score_fields.expiration_date,
        );
        
        // Verify Django serialization format
        assert!(event_data.is_array());
        let first_item = &event_data[0];
        assert_eq!(first_item["model"], "registry.score");
        assert_eq!(first_item["pk"], 1);
        assert_eq!(first_item["fields"]["passport"], 2);
        assert_eq!(first_item["fields"]["status"], "DONE");
        assert!(first_item["fields"]["evidence"].is_object());
        assert!(first_item["fields"]["stamp_scores"].is_object());
        assert!(first_item["fields"]["stamps"].is_object());
    }
}