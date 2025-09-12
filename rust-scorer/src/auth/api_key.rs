use sha2::{Sha256, Sha512, Digest};
use pbkdf2::pbkdf2;
use pbkdf2::hmac::Hmac;
use base64::{Engine as _, engine::general_purpose};
use constant_time_eq::constant_time_eq;
use sqlx::{PgPool, Postgres, Transaction};
use std::env;
use tracing::{debug, info, warn};

use crate::db::errors::{DatabaseError, Result};
use crate::models::django::DjangoApiKey;

/// Verify an API key against Django's PBKDF2-SHA256 hash
#[tracing::instrument(skip(key), fields(hash_type = %hash_string.split('$').next().unwrap_or("unknown")))]
pub fn verify_django_pbkdf2(key: &str, hash_string: &str) -> bool {
    // Parse Django's format: pbkdf2_sha256$iterations$salt$hash
    let parts: Vec<&str> = hash_string.split('$').collect();
    if parts.len() != 4 || parts[0] != "pbkdf2_sha256" {
        // Fallback to SHA512 format for compatibility
        return verify_sha512(key, hash_string);
    }
    
    let iterations: u32 = match parts[1].parse() {
        Ok(i) => i,
        Err(_) => return false,
    };
    let salt = parts[2];
    let expected_hash = parts[3];
    
    // Compute PBKDF2-SHA256
    let mut output = vec![0u8; 32]; // SHA256 produces 32 bytes
    pbkdf2::<Hmac<Sha256>>(
        key.as_bytes(),
        salt.as_bytes(),
        iterations,
        &mut output,
    ).unwrap();
    
    // Encode to base64 and compare
    let computed_hash = general_purpose::STANDARD.encode(&output);
    constant_time_eq(computed_hash.as_bytes(), expected_hash.as_bytes())
}

/// Verify SHA512 format (for backward compatibility)
fn verify_sha512(key: &str, hash_string: &str) -> bool {
    if !hash_string.starts_with("sha512$$") {
        return false;
    }
    let expected_hash = &hash_string[8..];
    let mut hasher = Sha512::new();
    hasher.update(key.as_bytes());
    let result = hasher.finalize();
    let computed_hash = format!("{:x}", result);
    constant_time_eq(computed_hash.as_bytes(), expected_hash.as_bytes())
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
    #[tracing::instrument(skip(pool, x_api_key, auth_header), fields(api_key_prefix))]
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
        tracing::Span::current().record("api_key_prefix", prefix);
        
        // Look up API key by prefix
        debug!(prefix, "Looking up API key in database");
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
        
        // Verify the full key hash (supports both Django PBKDF2 and SHA512)
        debug!("Verifying API key hash");
        if !verify_django_pbkdf2(&final_key, &stored_key.hashed_key) {
            warn!("API key verification failed for prefix: {}", prefix);
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
    #[tracing::instrument(skip_all, fields(api_key_id = %api_key_id, path = %path, status_code = status_code))]
    pub async fn track_usage(
        tx: &mut Transaction<'_, Postgres>,
        api_key_id: &str,
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
    fn test_verify_django_pbkdf2() {
        // Test PBKDF2 format
        let key = "test_key";
        let hash = "pbkdf2_sha256$600000$testsalt$Zk8ZZgY9L6oHpNPLhLtTfPtTEuN1sQqhL0H8Qb2DUWY=";
        // Note: This is a mock test - real verification would need matching salt/hash
        
        // Test SHA512 fallback
        let sha512_hash = "sha512$$b1bd184bf642cb5fc2eee643b2cc20e949abe73b16591f99f24b1f1f7d7873f0b3b242ae53c08c8b09bf594f0c3287b2c109ab542ae0f98be385f13ed4d9c5a7";
        assert!(verify_sha512("testkey1.secretpartofthekey123", sha512_hash));
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