use sha2::{Sha256, Digest};
use pbkdf2::pbkdf2;
use pbkdf2::hmac::Hmac;
use base64::{Engine as _, engine::general_purpose};
use constant_time_eq::constant_time_eq;
use sqlx::{PgPool, Postgres, Transaction};
use std::env;
use tracing::{debug, info, warn};

use crate::db::errors::{DatabaseError, Result};
use crate::models::django::DjangoApiKey;

/// Generate SHA-256 hash in Django format: "sha256$<hex>"
pub fn hash_key_sha256(key: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(key.as_bytes());
    let result = hasher.finalize();
    format!("sha256${:x}", result)
}

/// Verify SHA-256 hash (fast path - microseconds)
fn verify_sha256(key: &str, hash_string: &str) -> bool {
    if !hash_string.starts_with("sha256$") {
        return false;
    }
    let expected = hash_key_sha256(key);
    constant_time_eq(expected.as_bytes(), hash_string.as_bytes())
}

/// Verify an API key against Django's PBKDF2-SHA256 hash (slow path - ~88ms)
fn verify_pbkdf2(key: &str, hash_string: &str) -> bool {
    // Parse Django's format: pbkdf2_sha256$iterations$salt$hash
    let parts: Vec<&str> = hash_string.split('$').collect();
    if parts.len() != 4 || parts[0] != "pbkdf2_sha256" {
        return false;
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

enum VerificationResult {
    ValidSha256,
    ValidPbkdf2NeedsMigration,
    Invalid,
}

/// Verify API key with SHA-256 fast path and PBKDF2 fallback
#[tracing::instrument(skip(key, hashed_key, hashed_key_sha256))]
fn verify_api_key(
    key: &str,
    hashed_key: &str,
    hashed_key_sha256: Option<&str>,
) -> VerificationResult {
    // Fast path: SHA-256 (microseconds)
    if let Some(sha256_hash) = hashed_key_sha256 {
        if verify_sha256(key, sha256_hash) {
            debug!("API key verified using SHA-256 fast path");
            return VerificationResult::ValidSha256;
        }
        // If SHA-256 hash exists but doesn't match, key is invalid
        return VerificationResult::Invalid;
    }

    // Check if hashed_key itself is SHA-256 format (shouldn't happen, but handle it)
    if hashed_key.starts_with("sha256$") {
        if verify_sha256(key, hashed_key) {
            debug!("API key verified using SHA-256 (from hashed_key field)");
            return VerificationResult::ValidSha256;
        }
        return VerificationResult::Invalid;
    }

    // Slow fallback: PBKDF2 (~88ms average)
    if hashed_key.starts_with("pbkdf2_sha256$") {
        debug!("Using PBKDF2 fallback for API key verification");
        if verify_pbkdf2(key, hashed_key) {
            info!("API key verified with PBKDF2 - needs migration to SHA-256");
            return VerificationResult::ValidPbkdf2NeedsMigration;
        }
        return VerificationResult::Invalid;
    }

    // Unknown hash format
    warn!("Unknown hash format: {}", &hashed_key[..20.min(hashed_key.len())]);
    VerificationResult::Invalid
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
        path: &str,  // For analytics tracking
    ) -> Result<DjangoApiKey> {
        debug!("Validating API key");

        // Determine which key to use
        let api_key = if let Some(key) = x_api_key {
            key.to_string()
        } else if let Some(auth) = auth_header {
            // Extract from "Bearer <key>" or "Token <key>" format
            auth.split_whitespace()
                .nth(1)
                .ok_or_else(|| {
                    // Track failed auth - invalid header format
                    let pool_clone = pool.clone();
                    let path_clone = path.to_string();
                    tokio::spawn(async move {
                        let _ = ApiKeyValidator::track_failed_auth(&pool_clone, None, &path_clone).await;
                    });
                    DatabaseError::Unauthorized(
                        "Invalid Authorization header format".to_string()
                    )
                })?
                .to_string()
        } else {
            // Track failed auth - no API key provided
            let pool_clone = pool.clone();
            let path_clone = path.to_string();
            tokio::spawn(async move {
                let _ = ApiKeyValidator::track_failed_auth(&pool_clone, None, &path_clone).await;
            });
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
                hashed_key_sha256,
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
        .map_err(|e| {
            // Track failed auth - key not found or query error
            let pool_clone = pool.clone();
            let path_clone = path.to_string();
            let prefix_clone = prefix.to_string();
            tokio::spawn(async move {
                let _ = ApiKeyValidator::track_failed_auth(&pool_clone, Some(&prefix_clone), &path_clone).await;
            });

            match e {
                sqlx::Error::RowNotFound => DatabaseError::Unauthorized(
                    "Invalid or expired API key".to_string()
                ),
                _ => DatabaseError::QueryError(e),
            }
        })?;
        
        // Verify the full key hash with SHA-256 fast path and PBKDF2 fallback
        debug!("Verifying API key hash");
        let verification_result = verify_api_key(
            &final_key,
            &stored_key.hashed_key,
            stored_key.hashed_key_sha256.as_deref(),
        );

        match verification_result {
            VerificationResult::ValidSha256 => {
                // Fast path succeeded - no migration needed
            }
            VerificationResult::ValidPbkdf2NeedsMigration => {
                // Slow path succeeded - migrate to SHA-256 asynchronously
                let sha256_hash = hash_key_sha256(&final_key);
                let api_key_id = stored_key.id.clone();

                // Spawn migration task (fire and forget - don't block the request)
                let pool_clone = pool.clone();
                tokio::spawn(async move {
                    if let Err(e) = sqlx::query(
                        "UPDATE account_accountapikey SET hashed_key_sha256 = $1 WHERE id = $2"
                    )
                    .bind(&sha256_hash)
                    .bind(&api_key_id)
                    .execute(&pool_clone)
                    .await
                    {
                        warn!("Failed to migrate API key to SHA-256: {}", e);
                    } else {
                        info!("API key auto-migrated to SHA-256 for id: {}", api_key_id);
                    }
                });
            }
            VerificationResult::Invalid => {
                warn!("API key verification failed for prefix: {}", prefix);
                // Track failed auth - invalid key
                let pool_clone = pool.clone();
                let path_clone = path.to_string();
                let prefix_clone = prefix.to_string();
                tokio::spawn(async move {
                    let _ = ApiKeyValidator::track_failed_auth(&pool_clone, Some(&prefix_clone), &path_clone).await;
                });
                return Err(DatabaseError::Unauthorized(
                    "Invalid API key".to_string()
                ));
            }
        }

        // Check read_scores permission for scoring endpoints
        if !stored_key.read_scores {
            // Track failed auth - insufficient permissions
            let pool_clone = pool.clone();
            let path_clone = path.to_string();
            let prefix_clone = prefix.to_string();
            tokio::spawn(async move {
                let _ = ApiKeyValidator::track_failed_auth(&pool_clone, Some(&prefix_clone), &path_clone).await;
            });
            return Err(DatabaseError::Unauthorized(
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

    /// Track failed authentication attempt (matches Python's track_usage for 401s)
    #[tracing::instrument(skip(pool), fields(path = %path))]
    pub async fn track_failed_auth(
        pool: &PgPool,
        key_prefix: Option<&str>,
        path: &str,
    ) -> Result<()> {
        debug!("Tracking failed authentication attempt");

        // Try to look up API key by prefix (even if empty)
        let api_key_id: Option<String> = if let Some(prefix) = key_prefix {
            if !prefix.is_empty() {
                sqlx::query_scalar::<_, String>(
                    "SELECT id FROM account_accountapikey WHERE prefix = $1"
                )
                .bind(prefix)
                .fetch_optional(pool)
                .await
                .ok()
                .flatten()
            } else {
                None
            }
        } else {
            None
        };

        // Extract path segments
        let path_segments: Vec<&str> = path
            .split('/')
            .filter(|s| !s.is_empty())
            .collect();
        let base_path = path_segments.first().map(|s| s.to_string());

        // Insert analytics record with NULL api_key_id for failed auth
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
            ) VALUES ($1, NOW(), $2, $3, $4, NULL, NULL, NULL, NULL, true, $5, 401)
            "#
        )
        .bind(api_key_id)
        .bind(path)
        .bind(base_path)
        .bind(serde_json::to_value(&path_segments).unwrap())
        .bind("Unauthorized request")
        .execute(pool)
        .await
        .ok(); // Ignore errors in analytics tracking

        debug!("Failed auth tracked");
        Ok(())
    }
}

/// Convenience function for backward compatibility
pub async fn validate_api_key(
    pool: &PgPool,
    api_key_header: &str,
    path: &str,
) -> Result<DjangoApiKey> {
    ApiKeyValidator::validate(pool, Some(api_key_header), None, path).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hash_key_sha256() {
        // Test SHA-256 hash generation matches Python format
        let key = "testkey1.secretpartofthekey123";
        let hash = hash_key_sha256(key);

        // Verify format
        assert!(hash.starts_with("sha256$"));
        assert_eq!(hash.len(), 71); // "sha256$" (7 chars) + 64 hex chars

        // Verify consistency
        assert_eq!(hash, hash_key_sha256(key));

        // Verify different keys produce different hashes
        assert_ne!(hash, hash_key_sha256("different_key"));
    }

    #[test]
    fn test_verify_sha256() {
        let key = "testkey1.secretpartofthekey123";
        let correct_hash = hash_key_sha256(key);

        // Test correct key
        assert!(verify_sha256(key, &correct_hash));

        // Test incorrect key
        assert!(!verify_sha256("wrong_key", &correct_hash));

        // Test invalid format
        assert!(!verify_sha256(key, "invalid_format"));
        assert!(!verify_sha256(key, "sha512$$abcdef"));
    }

    #[test]
    fn test_verify_pbkdf2() {
        // Test valid PBKDF2 format detection
        let pbkdf2_hash = "pbkdf2_sha256$600000$testsalt$Zk8ZZgY9L6oHpNPLhLtTfPtTEuN1sQqhL0H8Qb2DUWY=";
        // Note: This will return false since the hash doesn't match,
        // but it tests the format parsing
        let _ = verify_pbkdf2("test_key", pbkdf2_hash);

        // Test invalid format
        assert!(!verify_pbkdf2("test_key", "invalid_format"));
        assert!(!verify_pbkdf2("test_key", "sha256$abc"));
    }

    #[test]
    fn test_verify_api_key_sha256_fast_path() {
        let key = "testkey1.secretpartofthekey123";
        let sha256_hash = hash_key_sha256(key);

        // Test SHA-256 fast path with hashed_key_sha256
        match verify_api_key(key, "unused", Some(&sha256_hash)) {
            VerificationResult::ValidSha256 => (),
            _ => panic!("Should use SHA-256 fast path"),
        }

        // Test SHA-256 fast path with wrong key
        match verify_api_key("wrong_key", "unused", Some(&sha256_hash)) {
            VerificationResult::Invalid => (),
            _ => panic!("Should be invalid"),
        }
    }

    #[test]
    fn test_verify_api_key_sha256_in_hashed_key() {
        let key = "testkey1.secretpartofthekey123";
        let sha256_hash = hash_key_sha256(key);

        // Test when SHA-256 is in hashed_key field (edge case)
        match verify_api_key(key, &sha256_hash, None) {
            VerificationResult::ValidSha256 => (),
            _ => panic!("Should detect SHA-256 in hashed_key"),
        }
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