use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};
use std::env;

use crate::api::error::ApiError;

/// JWT Claims structure matching Python's ninja_jwt
/// The JWT contains a 'did' claim with format: did:pkh:eip155:1:0xADDRESS
#[derive(Debug, Serialize, Deserialize)]
struct Claims {
    did: String,
    exp: i64,
}

/// Validate JWT token and extract Ethereum address from DID
///
/// This matches Python's JWTDidAuthentication behavior:
/// 1. Validate JWT signature using JWT_SECRET from environment
/// 2. Extract DID from claims (format: did:pkh:eip155:1:0xADDRESS)
/// 3. Return lowercased Ethereum address
pub fn validate_jwt_and_extract_address(token: &str) -> Result<String, ApiError> {
    // Get JWT_SECRET from environment, fallback to SECRET_KEY (matching Python's ninja_jwt SIGNING_KEY)
    let jwt_secret = env::var("JWT_SECRET")
        .or_else(|_| env::var("SECRET_KEY"))
        .map_err(|_| ApiError::Internal("JWT_SECRET or SECRET_KEY environment variable not set".to_string()))?
        .trim_matches('"')
        .to_string();

    // Create validation configuration
    // Match Python's ninja_jwt default: HS256 algorithm
    let mut validation = Validation::new(Algorithm::HS256);
    // Disable audience validation (Python doesn't use it for ceramic-cache)
    validation.validate_aud = false;

    // Decode and validate token
    let token_data = decode::<Claims>(
        token,
        &DecodingKey::from_secret(jwt_secret.as_ref()),
        &validation,
    )
    .map_err(|e| {
        tracing::warn!("JWT validation failed: {}", e);
        ApiError::Unauthorized(format!("Invalid JWT token: {}", e))
    })?;

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
