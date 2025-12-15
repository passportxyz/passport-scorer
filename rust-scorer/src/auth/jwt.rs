use base64::{engine::general_purpose::STANDARD, Engine};
use jsonwebtoken::{decode, decode_header, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};
use std::env;
use std::sync::OnceLock;

use crate::api::error::ApiError;

/// JWT Claims structure matching Python's ninja_jwt and SIWE JWT
/// The JWT contains a 'did' claim with format: did:pkh:eip155:1:0xADDRESS
#[derive(Debug, Serialize, Deserialize)]
struct Claims {
    did: String,
    exp: i64,
}

/// Cached SIWE JWT public key (decoded from base64 if needed)
static SIWE_PUBLIC_KEY: OnceLock<Option<String>> = OnceLock::new();

/// Decode base64-encoded PEM key, or return as-is if already PEM format
fn decode_pem_key(value: &str) -> String {
    // If it already looks like a PEM key, use it directly (for local dev)
    if value.contains("-----BEGIN") {
        return value.to_string();
    }
    // Otherwise, decode from base64
    match STANDARD.decode(value) {
        Ok(bytes) => String::from_utf8(bytes).unwrap_or_else(|_| value.to_string()),
        Err(_) => value.to_string(),
    }
}

/// Get SIWE JWT public key (cached, decoded from base64 if needed)
fn get_siwe_public_key() -> Option<&'static String> {
    SIWE_PUBLIC_KEY
        .get_or_init(|| {
            env::var("SIWE_JWT_PUBLIC_KEY")
                .ok()
                .filter(|s| !s.is_empty())
                .map(|s| decode_pem_key(&s))
        })
        .as_ref()
}

/// Validate JWT token and extract Ethereum address from DID
///
/// Supports two authentication methods:
/// 1. RS256 (SIWE) - Uses SIWE_JWT_PUBLIC_KEY for new SIWE-based authentication
/// 2. HS256 (legacy) - Uses SECRET_KEY for existing ninja_jwt authentication
///
/// The algorithm is detected from the JWT header.
pub fn validate_jwt_and_extract_address(token: &str) -> Result<String, ApiError> {
    // Peek at the JWT header to determine the algorithm
    let header = decode_header(token).map_err(|e| {
        tracing::warn!("Failed to decode JWT header: {}", e);
        ApiError::Unauthorized(format!("Invalid JWT token: {}", e))
    })?;

    let token_data = match header.alg {
        Algorithm::RS256 => {
            // SIWE authentication - use RS256 with public key
            let public_key = get_siwe_public_key().ok_or_else(|| {
                ApiError::Internal("SIWE_JWT_PUBLIC_KEY not configured".to_string())
            })?;

            let mut validation = Validation::new(Algorithm::RS256);
            validation.validate_aud = false;
            validation.set_issuer(&["passport-scorer"]);

            let decoding_key = DecodingKey::from_rsa_pem(public_key.as_bytes()).map_err(|e| {
                tracing::error!("Failed to parse SIWE_JWT_PUBLIC_KEY: {}", e);
                ApiError::Internal("Invalid SIWE_JWT_PUBLIC_KEY format".to_string())
            })?;

            decode::<Claims>(token, &decoding_key, &validation).map_err(|e| {
                tracing::warn!("RS256 JWT validation failed: {}", e);
                ApiError::Unauthorized(format!("Invalid JWT token: {}", e))
            })?
        }
        Algorithm::HS256 => {
            // Legacy authentication - use HS256 with secret key
            let jwt_secret = env::var("JWT_SECRET")
                .or_else(|_| env::var("SECRET_KEY"))
                .map_err(|_| {
                    ApiError::Internal(
                        "JWT_SECRET or SECRET_KEY environment variable not set".to_string(),
                    )
                })?
                .trim_matches('"')
                .to_string();

            let mut validation = Validation::new(Algorithm::HS256);
            validation.validate_aud = false;

            decode::<Claims>(
                token,
                &DecodingKey::from_secret(jwt_secret.as_ref()),
                &validation,
            )
            .map_err(|e| {
                tracing::warn!("HS256 JWT validation failed: {}", e);
                ApiError::Unauthorized(format!("Invalid JWT token: {}", e))
            })?
        }
        alg => {
            tracing::warn!("Unsupported JWT algorithm: {:?}", alg);
            return Err(ApiError::Unauthorized(format!(
                "Unsupported JWT algorithm: {:?}",
                alg
            )));
        }
    };

    // Extract address from DID format: did:pkh:eip155:1:0xADDRESS
    // Python's get_address_from_did: did.split(":")[-1]
    let address = token_data
        .claims
        .did
        .split(':')
        .last()
        .ok_or_else(|| ApiError::Validation("Invalid DID format in JWT".to_string()))?;

    // Return lowercased address to match Python behavior
    Ok(address.to_lowercase())
}

/// Extract JWT token from Authorization header
/// Expected format: "Bearer <token>"
pub fn extract_jwt_from_header(auth_header: Option<&str>) -> Result<&str, ApiError> {
    let auth_value = auth_header.ok_or_else(|| {
        ApiError::Unauthorized("Missing Authorization header".to_string())
    })?;

    // Strip "Bearer " prefix
    auth_value
        .strip_prefix("Bearer ")
        .ok_or_else(|| {
            ApiError::Unauthorized("Invalid Authorization header format, expected 'Bearer <token>'".to_string())
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_jwt_from_header_valid() {
        let header = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token";
        let result = extract_jwt_from_header(Some(header));
        assert!(result.is_ok());
        assert_eq!(
            result.unwrap(),
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"
        );
    }

    #[test]
    fn test_extract_jwt_from_header_missing() {
        let result = extract_jwt_from_header(None);
        assert!(result.is_err());
        match result {
            Err(ApiError::Unauthorized(msg)) => {
                assert!(msg.contains("Missing Authorization header"));
            }
            _ => panic!("Expected Unauthorized error"),
        }
    }

    #[test]
    fn test_extract_jwt_from_header_invalid_format() {
        let header = "InvalidFormat token";
        let result = extract_jwt_from_header(Some(header));
        assert!(result.is_err());
        match result {
            Err(ApiError::Unauthorized(msg)) => {
                assert!(msg.contains("Invalid Authorization header format"));
            }
            _ => panic!("Expected Unauthorized error"),
        }
    }

    #[test]
    fn test_extract_jwt_from_header_no_token() {
        let header = "Bearer ";
        let result = extract_jwt_from_header(Some(header));
        // This will succeed but return empty string - validation will fail later
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "");
    }

    // Note: Full JWT validation tests require setting JWT_SECRET env var
    // and creating valid JWT tokens. These are better suited for integration tests.
    // Here we just test the helper functions.
}
