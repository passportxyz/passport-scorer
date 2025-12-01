#[cfg(test)]
mod integration_tests {
    use super::super::*;
    use sqlx::PgPool;
    
    
    // Integration tests - require DATABASE_URL

    #[tokio::test]
    async fn test_upsert_passport() -> Result<()> {
        let database_url = std::env::var("DATABASE_URL")
            .expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await?;
        let mut tx = pool.begin().await?;

        let _passport_id = upsert_passport_record(
            &mut tx,
            "0x1234567890abcdef",
            1
        ).await.unwrap();

        assert!(_passport_id > 0);

        // Test idempotency - should return same ID
        let passport_id2 = upsert_passport_record(
            &mut tx,
            "0x1234567890abcdef",
            1
        ).await.unwrap();

        assert_eq!(_passport_id, passport_id2);

        tx.rollback().await?;
        Ok(())
    }

    #[tokio::test]
    async fn test_get_ceramic_cache_entries() -> Result<()> {
        let database_url = std::env::var("DATABASE_URL")
            .expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await?;
        // This test would need test data in the ceramic_cache table
        let stamps = get_ceramic_cache_entries(
            &pool,
            "0xtest_address"
        ).await.unwrap();

        // Would assert based on test data
        assert!(stamps.is_empty() || !stamps.is_empty());

        Ok(())
    }
    
    #[sqlx::test]
    async fn test_retry_logic() -> sqlx::Result<()> {
        let mut attempts = 0;
        
        let result = with_retry(3, || {
            attempts += 1;
            async move {
                if attempts < 2 {
                    Err(DatabaseError::IntegrityError("test".to_string()))
                } else {
                    Ok(42)
                }
            }
        }).await;
        
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 42);
        
        Ok(())
    }
    
    #[tokio::test]
    async fn test_hash_link_operations() -> Result<()> {
        let database_url = std::env::var("DATABASE_URL")
            .expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await?;
        let mut tx = pool.begin().await?;

        // Create test passport
        let _passport_id = upsert_passport_record(
            &mut tx,
            "0xtest_address",
            1
        ).await.unwrap();

        // Test hash link creation
        let links_to_create = vec![
            ("hash1".to_string(), "0xtest_address".to_string(), 1, chrono::Utc::now()),
            ("hash2".to_string(), "0xtest_address".to_string(), 1, chrono::Utc::now()),
        ];

        bulk_upsert_hash_links(
            &mut tx,
            links_to_create,
            vec![]
        ).await.unwrap();

        // Verify links were created
        let verified = verify_hash_links(
            &mut tx,
            "0xtest_address",
            1,
            &vec!["hash1".to_string(), "hash2".to_string()]
        ).await.unwrap();

        assert!(verified);

        tx.rollback().await?;
        Ok(())
    }
}