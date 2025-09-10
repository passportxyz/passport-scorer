use once_cell::sync::OnceCell;
use sqlx::postgres::{PgPool, PgPoolOptions};
use std::time::Duration;
use tracing::{info, warn};

use crate::db::errors::{DatabaseError, Result};

static DB_POOL: OnceCell<PgPool> = OnceCell::new();

/// Initialize the database connection pool
/// This should be called once at application startup
pub async fn init_pool() -> Result<()> {
    let database_url = std::env::var("DATABASE_URL")
        .or_else(|_| std::env::var("RDS_PROXY_URL"))
        .map_err(|_| DatabaseError::ConnectionError(
            "DATABASE_URL or RDS_PROXY_URL environment variable not set".to_string()
        ))?;
    
    info!("Initializing database connection pool");
    
    let pool = PgPoolOptions::new()
        // Keep pool size low - RDS Proxy handles actual pooling
        .max_connections(5)
        .min_connections(0)  // Allow scaling to zero for Lambda
        .acquire_timeout(Duration::from_secs(3))
        .idle_timeout(Duration::from_secs(10))
        .max_lifetime(Duration::from_secs(300))  // 5 minutes
        // Test connection on checkout to ensure it's still valid
        .test_before_acquire(true)
        .connect_lazy(&database_url)
        .map_err(|e| DatabaseError::ConnectionError(format!("Failed to create pool: {}", e)))?;
    
    // Test the connection
    sqlx::query("SELECT 1")
        .fetch_one(&pool)
        .await
        .map_err(|e| DatabaseError::ConnectionError(format!("Failed to test connection: {}", e)))?;
    
    DB_POOL.set(pool)
        .map_err(|_| DatabaseError::ConnectionError("Pool already initialized".to_string()))?;
    
    info!("Database connection pool initialized successfully");
    Ok(())
}

/// Get a reference to the database pool
pub fn get_pool() -> Result<&'static PgPool> {
    DB_POOL.get()
        .ok_or_else(|| DatabaseError::ConnectionError(
            "Database pool not initialized. Call init_pool() first".to_string()
        ))
}

/// Create a new pool for testing or isolated operations
pub async fn create_pool(database_url: &str) -> Result<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .acquire_timeout(Duration::from_secs(3))
        .connect(database_url)
        .await
        .map_err(|e| DatabaseError::ConnectionError(format!("Failed to create pool: {}", e)))?;
    
    Ok(pool)
}

/// Close the database pool (useful for cleanup)
pub async fn close_pool() -> Result<()> {
    if let Some(pool) = DB_POOL.get() {
        pool.close().await;
        info!("Database pool closed");
    }
    Ok(())
}

/// Health check for the database connection
pub async fn health_check() -> Result<()> {
    let pool = get_pool()?;
    
    sqlx::query("SELECT 1")
        .fetch_one(pool)
        .await
        .map_err(|e| DatabaseError::QueryError(e))?;
    
    Ok(())
}

/// Execute a function with retry logic for handling transient errors
pub async fn with_retry<F, Fut, T>(
    max_retries: u8,
    mut operation: F,
) -> Result<T>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<T>>,
{
    let mut attempt = 0;
    
    loop {
        attempt += 1;
        
        match operation().await {
            Ok(result) => return Ok(result),
            Err(e) if e.is_retryable() && attempt < max_retries => {
                warn!(
                    attempt = attempt,
                    max_retries = max_retries,
                    error = %e,
                    "Retryable error occurred, retrying..."
                );
                
                // Exponential backoff with jitter
                let delay_ms = (50 * 2_u64.pow(attempt as u32 - 1))
                    .min(1000)  // Cap at 1 second
                    + (rand::random::<u64>() % 50);  // Add 0-50ms jitter
                
                tokio::time::sleep(Duration::from_millis(delay_ms)).await;
            }
            Err(_) if attempt >= max_retries => {
                return Err(DatabaseError::RetryLimitExceeded { attempts: max_retries });
            }
            Err(e) => return Err(e),
        }
    }
}

// Helper function for random jitter (simple implementation)
mod rand {
    use std::collections::hash_map::RandomState;
    use std::hash::{BuildHasher, Hash, Hasher};
    
    pub fn random<T>() -> T
    where
        T: Default + From<u64>,
    {
        let mut hasher = RandomState::new().build_hasher();
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
            .hash(&mut hasher);
        T::from(hasher.finish())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_retry_logic() {
        let mut call_count = 0;
        
        let result = with_retry(3, || {
            call_count += 1;
            async move {
                if call_count < 3 {
                    Err(DatabaseError::IntegrityError("test error".to_string()))
                } else {
                    Ok(42)
                }
            }
        }).await;
        
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 42);
    }
    
    #[tokio::test]
    async fn test_retry_limit_exceeded() {
        let mut call_count = 0;
        
        let result = with_retry(2, || {
            call_count += 1;
            async move {
                Err(DatabaseError::IntegrityError("test error".to_string()))
            }
        }).await;
        
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), DatabaseError::RetryLimitExceeded { .. }));
    }
}