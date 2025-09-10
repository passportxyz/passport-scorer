// Integration tests for LIFO deduplication
// Run with: cargo test --test lifo_integration -- --nocapture

use chrono::{Duration, Utc};
use passport_scorer::{lifo_dedup, LifoResult, ValidStamp};
use rust_decimal::prelude::*;
use serde_json::json;
use sqlx::PgPool;
use std::collections::HashMap;
use std::env;

async fn setup_test_db() -> PgPool {
    // Use test database URL from environment or default
    let database_url = env::var("TEST_DATABASE_URL")
        .unwrap_or_else(|_| env::var("DATABASE_URL")
            .expect("DATABASE_URL must be set for tests"));
    
    PgPool::connect(&database_url)
        .await
        .expect("Failed to connect to test database")
}

fn create_test_stamp(provider: &str, nullifiers: Vec<String>) -> ValidStamp {
    ValidStamp {
        provider: provider.to_string(),
        credential: json!({
            "credentialSubject": {
                "provider": provider,
                "nullifiers": nullifiers.clone(),
                "id": "did:pkh:eip155:1:0xtest"
            },
            "issuer": "did:key:test",
            "expirationDate": (Utc::now() + Duration::days(30)).to_rfc3339(),
        }),
        nullifiers,
        expires_at: Utc::now() + Duration::days(30),
    }
}

fn create_test_weights() -> HashMap<String, Decimal> {
    let mut weights = HashMap::new();
    weights.insert("Google".to_string(), Decimal::from_str("1.5").unwrap());
    weights.insert("Twitter".to_string(), Decimal::from_str("2.0").unwrap());
    weights.insert("Github".to_string(), Decimal::from_str("3.0").unwrap());
    weights.insert("Discord".to_string(), Decimal::from_str("1.0").unwrap());
    weights
}

#[tokio::test]
async fn test_lifo_no_existing_links() {
    let pool = setup_test_db().await;
    let mut tx = pool.begin().await.unwrap();
    
    let address = "0xtest_no_existing_99999";
    let community_id = 99999;
    let weights = create_test_weights();
    
    // Clean up any existing test data
    sqlx::query("DELETE FROM registry_hashscorerlink WHERE address = $1 AND community_id = $2")
        .bind(address)
        .bind(community_id)
        .execute(&mut *tx)
        .await
        .ok();
    
    // Create stamps with unique nullifiers
    let stamps = vec![
        create_test_stamp("Google", vec!["test_null_google_1".to_string()]),
        create_test_stamp("Twitter", vec!["test_null_twitter_1".to_string(), "test_null_twitter_2".to_string()]),
    ];
    
    // Run LIFO deduplication
    let result = lifo_dedup(&stamps, address, community_id, &weights, &mut tx)
        .await
        .expect("LIFO dedup should succeed");
    
    // All stamps should be valid (no clashes)
    assert_eq!(result.valid_stamps.len(), 2);
    assert_eq!(result.clashing_stamps.len(), 0);
    assert_eq!(result.hash_links_processed, 3); // 3 nullifiers total
    
    // Verify stamps have correct weights
    let google_stamp = result.valid_stamps.iter()
        .find(|s| s.provider == "Google")
        .expect("Google stamp should exist");
    assert_eq!(google_stamp.weight, Decimal::from_str("1.5").unwrap());
    assert!(!google_stamp.was_deduped);
    
    // Clean up
    tx.rollback().await.unwrap();
}

#[tokio::test]
async fn test_lifo_with_clashing_links() {
    let pool = setup_test_db().await;
    let mut tx = pool.begin().await.unwrap();
    
    let address1 = "0xtest_clash_owner1_99998";
    let address2 = "0xtest_clash_owner2_99998";
    let community_id = 99998;
    let weights = create_test_weights();
    
    // Clean up any existing test data
    sqlx::query("DELETE FROM registry_hashscorerlink WHERE community_id = $1")
        .bind(community_id)
        .execute(&mut *tx)
        .await
        .ok();
    
    // First, create hash links for address1
    let expires_future = Utc::now() + Duration::days(30);
    sqlx::query(
        "INSERT INTO registry_hashscorerlink (hash, address, community_id, expires_at) \
         VALUES ($1, $2, $3, $4) ON CONFLICT (hash, community_id) DO NOTHING"
    )
    .bind("test_null_shared_1")
    .bind(address1)
    .bind(community_id)
    .bind(expires_future)
    .execute(&mut *tx)
    .await
    .unwrap();
    
    // Now address2 tries to claim stamps with clashing nullifier
    let stamps = vec![
        create_test_stamp("Github", vec!["test_null_shared_1".to_string(), "test_null_github_2".to_string()]),
        create_test_stamp("Discord", vec!["test_null_discord_1".to_string()]),
    ];
    
    // Run LIFO deduplication for address2
    let result = lifo_dedup(&stamps, address2, community_id, &weights, &mut tx)
        .await
        .expect("LIFO dedup should succeed");
    
    // Github stamp should be clashing, Discord should be valid
    assert_eq!(result.valid_stamps.len(), 1);
    assert_eq!(result.clashing_stamps.len(), 1);
    
    // Verify Discord stamp is valid
    assert_eq!(result.valid_stamps[0].provider, "Discord");
    assert_eq!(result.valid_stamps[0].weight, Decimal::from_str("1.0").unwrap());
    
    // Verify Github stamp is clashing
    assert!(result.clashing_stamps.contains_key("Github"));
    let github_clash = &result.clashing_stamps["Github"];
    assert_eq!(github_clash.nullifiers.len(), 2);
    
    // Clean up
    tx.rollback().await.unwrap();
}

#[tokio::test]
async fn test_lifo_expired_takeover() {
    let pool = setup_test_db().await;
    let mut tx = pool.begin().await.unwrap();
    
    let address1 = "0xtest_expired_owner_99997";
    let address2 = "0xtest_new_owner_99997";
    let community_id = 99997;
    let weights = create_test_weights();
    
    // Clean up any existing test data
    sqlx::query("DELETE FROM registry_hashscorerlink WHERE community_id = $1")
        .bind(community_id)
        .execute(&mut *tx)
        .await
        .ok();
    
    // Create expired hash link for address1
    let expires_past = Utc::now() - Duration::days(1);
    sqlx::query(
        "INSERT INTO registry_hashscorerlink (hash, address, community_id, expires_at) \
         VALUES ($1, $2, $3, $4) ON CONFLICT (hash, community_id) DO NOTHING"
    )
    .bind("test_null_expired_1")
    .bind(address1)
    .bind(community_id)
    .bind(expires_past)
    .execute(&mut *tx)
    .await
    .unwrap();
    
    // Now address2 tries to claim stamp with expired nullifier
    let stamps = vec![
        create_test_stamp("Google", vec!["test_null_expired_1".to_string()]),
    ];
    
    // Run LIFO deduplication for address2
    let result = lifo_dedup(&stamps, address2, community_id, &weights, &mut tx)
        .await
        .expect("LIFO dedup should succeed");
    
    // Stamp should be valid (expired link can be taken over)
    assert_eq!(result.valid_stamps.len(), 1);
    assert_eq!(result.clashing_stamps.len(), 0);
    assert_eq!(result.valid_stamps[0].provider, "Google");
    
    // Clean up
    tx.rollback().await.unwrap();
}

#[tokio::test]
async fn test_lifo_partial_clash_with_backfill() {
    let pool = setup_test_db().await;
    let mut tx = pool.begin().await.unwrap();
    
    let address1 = "0xtest_partial_owner1_99996";
    let address2 = "0xtest_partial_owner2_99996";
    let community_id = 99996;
    let weights = create_test_weights();
    
    // Clean up any existing test data
    sqlx::query("DELETE FROM registry_hashscorerlink WHERE community_id = $1")
        .bind(community_id)
        .execute(&mut *tx)
        .await
        .ok();
    
    // First, address1 claims a stamp with multiple nullifiers
    let expires_future = Utc::now() + Duration::days(30);
    
    // Only create hash link for ONE of the nullifiers (simulating partial claim)
    sqlx::query(
        "INSERT INTO registry_hashscorerlink (hash, address, community_id, expires_at) \
         VALUES ($1, $2, $3, $4) ON CONFLICT (hash, community_id) DO NOTHING"
    )
    .bind("test_null_partial_1")
    .bind(address1)
    .bind(community_id)
    .bind(expires_future)
    .execute(&mut *tx)
    .await
    .unwrap();
    
    // Now address2 tries to claim stamp with partially clashing nullifiers
    let stamps = vec![
        create_test_stamp("Twitter", vec![
            "test_null_partial_1".to_string(),  // This one clashes
            "test_null_partial_2".to_string(),  // This one doesn't exist yet
            "test_null_partial_3".to_string(),  // This one doesn't exist yet
        ]),
    ];
    
    // Run LIFO deduplication for address2
    let result = lifo_dedup(&stamps, address2, community_id, &weights, &mut tx)
        .await
        .expect("LIFO dedup should succeed");
    
    // Twitter stamp should be clashing (because one nullifier clashes)
    assert_eq!(result.valid_stamps.len(), 0);
    assert_eq!(result.clashing_stamps.len(), 1);
    assert!(result.clashing_stamps.contains_key("Twitter"));
    
    // Verify backfill: non-clashing nullifiers should be created for address1
    let backfilled_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM registry_hashscorerlink \
         WHERE community_id = $1 AND hash IN ($2, $3) AND address = $4"
    )
    .bind(community_id)
    .bind("test_null_partial_2")
    .bind("test_null_partial_3")
    .bind(address1)  // Should belong to address1 (the clashing owner)
    .fetch_one(&mut *tx)
    .await
    .unwrap();
    
    assert_eq!(backfilled_count, 2, "Both backfilled nullifiers should belong to clashing owner");
    
    // Clean up
    tx.rollback().await.unwrap();
}

#[tokio::test]
async fn test_lifo_self_owned_update() {
    let pool = setup_test_db().await;
    let mut tx = pool.begin().await.unwrap();
    
    let address = "0xtest_self_owned_99995";
    let community_id = 99995;
    let weights = create_test_weights();
    
    // Clean up any existing test data
    sqlx::query("DELETE FROM registry_hashscorerlink WHERE community_id = $1")
        .bind(community_id)
        .execute(&mut *tx)
        .await
        .ok();
    
    // Create existing hash link owned by same address
    let old_expires = Utc::now() + Duration::days(10);
    sqlx::query(
        "INSERT INTO registry_hashscorerlink (hash, address, community_id, expires_at) \
         VALUES ($1, $2, $3, $4) ON CONFLICT (hash, community_id) DO NOTHING"
    )
    .bind("test_null_self_1")
    .bind(address)
    .bind(community_id)
    .bind(old_expires)
    .execute(&mut *tx)
    .await
    .unwrap();
    
    // Same address claims stamp with same nullifier but different expiration
    let stamps = vec![
        create_test_stamp("Google", vec!["test_null_self_1".to_string()]),
    ];
    
    // Run LIFO deduplication
    let result = lifo_dedup(&stamps, address, community_id, &weights, &mut tx)
        .await
        .expect("LIFO dedup should succeed");
    
    // Stamp should be valid (self-owned)
    assert_eq!(result.valid_stamps.len(), 1);
    assert_eq!(result.clashing_stamps.len(), 0);
    
    // Clean up
    tx.rollback().await.unwrap();
}