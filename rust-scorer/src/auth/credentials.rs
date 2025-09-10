use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashSet;
use tracing::{debug, info, warn};

use crate::db::errors::{DatabaseError, Result};

/// List of trusted IAM issuers - hardcoded for now but easy to make configurable
const TRUSTED_IAM_ISSUERS: &[&str] = &[
    "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "did:key:z6MkgfaeGaQe4R3yV9hmZnJhfWqgGJnCPfuQCbDBpDwYREQV",
    // Add more issuers as needed
];

/// Represents a validated credential
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidatedCredential {
    pub provider: String,
    pub credential: Value,
    pub nullifiers: Vec<String>,
    pub expires_at: DateTime<Utc>,
}

/// Validate a single credential
pub async fn validate_credential(
    credential: &Value,
    address: &str,
) -> Result<Option<ValidatedCredential>> {
    debug!("Validating credential for address: {}", address);
    
    // Extract credential subject
    let credential_subject = credential
        .get("credentialSubject")
        .ok_or_else(|| DatabaseError::InvalidData(
            "Missing credentialSubject".to_string()
        ))?;
    
    // Check provider
    let provider = credential_subject
        .get("provider")
        .and_then(|p| p.as_str())
        .ok_or_else(|| DatabaseError::InvalidData(
            "Missing provider".to_string()
        ))?;
    
    // Extract nullifiers (only support array, not hash field)
    let nullifiers = credential_subject
        .get("nullifiers")
        .and_then(|n| n.as_array())
        .ok_or_else(|| DatabaseError::InvalidData(
            "Missing or invalid nullifiers array".to_string()
        ))?;
    
    if nullifiers.is_empty() {
        warn!("Credential has empty nullifiers array");
        return Ok(None);
    }
    
    let nullifier_strings: Vec<String> = nullifiers
        .iter()
        .filter_map(|n| n.as_str().map(String::from))
        .collect();
    
    if nullifier_strings.len() != nullifiers.len() {
        warn!("Some nullifiers are not strings");
        return Ok(None);
    }
    
    // Check DID matches address
    let expected_did = format!("did:pkh:eip155:1:{}", address.to_lowercase());
    let credential_did = credential_subject
        .get("id")
        .and_then(|id| id.as_str())
        .map(|s| s.to_lowercase());
    
    if credential_did != Some(expected_did.clone()) {
        warn!("DID mismatch: expected {}, got {:?}", expected_did, credential_did);
        return Ok(None);
    }
    
    // Check expiration
    let expiration_date = credential
        .get("expirationDate")
        .and_then(|e| e.as_str())
        .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
        .map(|dt| dt.with_timezone(&Utc));
    
    let expires_at = expiration_date.ok_or_else(|| DatabaseError::InvalidData(
        "Missing or invalid expirationDate".to_string()
    ))?;
    
    if expires_at < Utc::now() {
        debug!("Credential expired at {}", expires_at);
        return Ok(None);
    }
    
    // Check issuer
    let issuer = credential
        .get("issuer")
        .and_then(|i| i.as_str());
    
    if !issuer.map(|i| TRUSTED_IAM_ISSUERS.contains(&i)).unwrap_or(false) {
        warn!("Untrusted issuer: {:?}", issuer);
        return Ok(None);
    }
    
    // Verify the credential signature using didkit's underlying ssi library
    // The Python didkit FFI wraps this Rust functionality
    use didkit::ssi::vc::{Credential, LinkedDataProofOptions, ProofPurpose};
    use didkit::ssi::jsonld::ContextLoader;
    use didkit::DID_METHODS;
    
    // Parse the credential
    let vc: Credential = serde_json::from_value(credential.clone())
        .map_err(|e| {
            warn!("Failed to parse credential: {}", e);
            DatabaseError::InvalidData(format!("Invalid credential format: {}", e))
        })?;
    
    // Set up verification options to match Python's {"proofPurpose":"assertionMethod"}
    let proof_options = LinkedDataProofOptions {
        proof_purpose: Some(ProofPurpose::AssertionMethod),
        ..Default::default()
    };
    
    // Verify the credential
    let resolver = DID_METHODS.to_resolver();
    let mut context_loader = ContextLoader::default();
    let result = vc.verify(Some(proof_options), &*resolver, &mut context_loader).await;
    
    // Check verification result
    if !result.errors.is_empty() {
        warn!("Credential verification failed: {:?}", result.errors);
        return Ok(None);
    }
    
    debug!("Credential signature verified successfully");
    
    info!("Credential validated successfully for provider: {}", provider);
    
    Ok(Some(ValidatedCredential {
        provider: provider.to_string(),
        credential: credential.clone(),
        nullifiers: nullifier_strings,
        expires_at,
    }))
}

/// Validate multiple credentials
pub async fn validate_credentials_batch(
    credentials: &[Value],
    address: &str,
) -> Result<Vec<ValidatedCredential>> {
    let mut valid_credentials = Vec::new();
    let mut seen_providers = HashSet::new();
    
    for credential in credentials {
        match validate_credential(credential, address).await {
            Ok(Some(valid)) => {
                // Only keep first credential per provider
                if seen_providers.insert(valid.provider.clone()) {
                    valid_credentials.push(valid);
                } else {
                    debug!("Skipping duplicate provider: {}", valid.provider);
                }
            }
            Ok(None) => {
                debug!("Credential validation returned None");
            }
            Err(e) => {
                warn!("Error validating credential: {}", e);
            }
        }
    }
    
    info!("Validated {} credentials out of {}", valid_credentials.len(), credentials.len());
    Ok(valid_credentials)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[tokio::test]
    async fn test_validate_credential_missing_fields() {
        let credential = json!({});
        let result = validate_credential(&credential, "0x123").await;
        assert!(result.is_err());
    }
    
    #[tokio::test]
    async fn test_validate_credential_expired() {
        let credential = json!({
            "credentialSubject": {
                "id": "did:pkh:eip155:1:0x123",
                "provider": "test",
                "nullifiers": ["null1", "null2"]
            },
            "expirationDate": "2020-01-01T00:00:00Z",
            "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC"
        });
        
        let result = validate_credential(&credential, "0x123").await.unwrap();
        assert!(result.is_none(), "Expired credential should return None");
    }
}