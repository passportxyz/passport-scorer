use sha2::{Sha512, Digest};
use sqlx::{PgPool, Postgres, Transaction};
use std::env;
use tracing::{debug, info, warn};

use crate::db::errors::{DatabaseError, Result};
use crate::models::django::DjangoApiKey;

/// Hash an API key using SHA512 (matching djangorestframework-api-key v2)
pub fn hash_api_key(key: &str) -> String {
    let mut hasher = Sha512::new();
    hasher.update(key.as_bytes());
    let result = hasher.finalize();
    format!("sha512$${:x}", result)
}

/// Extract the 8-character prefix from an API key
pub fn extract_prefix(key: &str) -> &str {
    if key.len() >= 8 {
        &key[..8]
    } else {
        key
    }
}

/// Check if the provided key matches one of the demo aliases
fn is_demo_alias(key: &str) -> bool {
    // In production, these would come from environment
    let demo_aliases = vec!["demo", "test", "sandbox"];
    demo_aliases.contains(&key)
}

/// Get demo API key from environment
fn get_demo_key() -> Option<String> {
    env::var("DEMO_API_KEY").ok()
}

pub struct ApiKeyValidator;

impl ApiKeyValidator {
    /// Validate an API key and return the key data
    /// Checks X-API-Key header first, then Authorization header
    pub async fn validate(
        pool: &PgPool,
        x_api_key: Option<&str>,
        auth_header: Option<&str>,
    ) -> Result<DjangoApiKey> {
        debug!("Validating API key");
        
        // Determine which key to use
        let api_key = if let Some(key) = x_api_key {
            key.to_string()
        } else if let Some(auth) = auth_header {
            // Extract from "Bearer <key>" or "Token <key>" format
            auth.split_whitespace()
                .nth(1)
                .ok_or_else(|| DatabaseError::InvalidData(
                    "Invalid Authorization header format".to_string()
                ))?
                .to_string()
        } else {
            return Err(DatabaseError::Unauthorized(
                "No API key provided".to_string()
            ));
        };
        
        // Check for demo aliases and replace with actual demo key
        let final_key = if is_demo_alias(&api_key) {
            get_demo_key().ok_or_else(|| DatabaseError::InvalidData(
                "Demo key not configured".to_string()
            ))?
        } else {
            api_key
        };
        
        // Extract prefix for database lookup
        let prefix = extract_prefix(&final_key);
        
        // Look up API key by prefix
        let stored_key = sqlx::query_as::<_, DjangoApiKey>(
            r#"
            SELECT
                id,
                prefix,
                hashed_key,
                account_id,
                name,
                revoked,
                submit_passports,
                read_scores,
                create_scorers,
                created,
                expiry_date
            FROM account_accountapikey
            WHERE prefix = $1
                AND revoked = false
                AND (expiry_date IS NULL OR expiry_date > NOW())
            "#
        )
        .bind(prefix)
        .fetch_one(pool)
        .await
        .map_err(|e| match e {
            sqlx::Error::RowNotFound => DatabaseError::NotFound(
                "Invalid or expired API key".to_string()
            ),
            _ => DatabaseError::QueryError(e),
        })?;
        
        // Verify the full key hash
        let computed_hash = hash_api_key(&final_key);
        if computed_hash != stored_key.hashed_key {
            warn!("API key hash mismatch for prefix: {}", prefix);
            return Err(DatabaseError::InvalidData(
                "Invalid API key".to_string()
            ));
        }
        
        // Check read_scores permission for scoring endpoints
        if !stored_key.read_scores {
            return Err(DatabaseError::InvalidData(
                "API key lacks read_scores permission".to_string()
            ));
        }
        
        info!("API key validated successfully");
        Ok(stored_key)
    }
    
    /// Track API key usage in analytics table
    pub async fn track_usage(
        tx: &mut Transaction<'_, Postgres>,
        api_key_id: i32,
        path: &str,
        _method: &str,
        status_code: i32,
        query_params: Option<serde_json::Value>,
        headers: Option<serde_json::Value>,
        payload: Option<serde_json::Value>,
        response: Option<serde_json::Value>,
        error: Option<String>,
    ) -> Result<()> {
        debug!("Tracking API key usage");
        
        // Extract path segments (skip empty first element from leading /)
        let path_segments: Vec<&str> = path
            .split('/')
            .filter(|s| !s.is_empty())
            .collect();
        
        // Determine base path (first segment or "/")
        let base_path = path_segments.first().map(|s| s.to_string());
        
        sqlx::query(
            r#"
            INSERT INTO account_accountapikeyanalytics (
                api_key_id,
                created_at,
                path,
                base_path,
                path_segments,
                query_params,
                headers,
                payload,
                response,
                response_skipped,
                error,
                status_code
            ) VALUES ($1, NOW(), $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            "#
        )
        .bind(api_key_id)
        .bind(path)
        .bind(base_path)
        .bind(serde_json::to_value(&path_segments).unwrap())
        .bind(query_params)
        .bind(headers)
        .bind(payload)
        .bind(&response)
        .bind(response.is_none()) // response_skipped
        .bind(error)
        .bind(status_code)
        .execute(&mut **tx)
        .await
        .map_err(DatabaseError::QueryError)?;
        
        debug!("API key usage tracked");
        Ok(())
    }
}

/// Convenience function for backward compatibility
pub async fn validate_api_key(
    pool: &PgPool,
    api_key_header: &str,
) -> Result<DjangoApiKey> {
    ApiKeyValidator::validate(pool, Some(api_key_header), None).await
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_hash_api_key() {
        let key = "testkey1.secretpartofthekey123";
        let expected = "sha512$$b1bd184bf642cb5fc2eee643b2cc20e949abe73b16591f99f24b1f1f7d7873f0b3b242ae53c08c8b09bf594f0c3287b2c109ab542ae0f98be385f13ed4d9c5a7";
        
        let hashed = hash_api_key(key);
        assert_eq!(hashed, expected, "Hash should match Python implementation");
    }
    
    #[test]
    fn test_extract_prefix() {
        assert_eq!(extract_prefix("abcd1234.secret"), "abcd1234");
        assert_eq!(extract_prefix("test"), "test");
        assert_eq!(extract_prefix("12345678901"), "12345678");
    }
    
    #[test]
    fn test_demo_aliases() {
        assert!(is_demo_alias("demo"));
        assert!(is_demo_alias("test"));
        assert!(!is_demo_alias("production"));
    }
}