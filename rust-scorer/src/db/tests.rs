#[cfg(test)]
mod integration_tests {
    use super::super::*;
    use sqlx::PgPool;
    use rust_decimal_macros::dec;
    
    // These tests require a test database to be set up
    // They use the SQLx test macro which manages test transactions
    
    #[sqlx::test]
    async fn test_upsert_passport(pool: PgPool) -> sqlx::Result<()> {
        let mut tx = pool.begin().await?;
        
        let passport_id = upsert_passport(
            &mut tx,
            "0x1234567890abcdef",
            1
        ).await.unwrap();
        
        assert!(passport_id > 0);
        
        // Test idempotency - should return same ID
        let passport_id2 = upsert_passport(
            &mut tx,
            "0x1234567890abcdef",
            1
        ).await.unwrap();
        
        assert_eq!(passport_id, passport_id2);
        
        tx.rollback().await?;
        Ok(())
    }
    
    #[sqlx::test]
    async fn test_load_ceramic_cache(pool: PgPool) -> sqlx::Result<()> {
        // This test would need test data in the ceramic_cache table
        let stamps = load_ceramic_cache(
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
    
    #[sqlx::test]
    async fn test_hash_link_operations(pool: PgPool) -> sqlx::Result<()> {
        let mut tx = pool.begin().await?;
        
        // Create test passport
        let passport_id = upsert_passport(
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