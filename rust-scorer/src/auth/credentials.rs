use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashSet;
use std::sync::OnceLock;
use tracing::{debug, info, warn};

use crate::db::errors::{DatabaseError, Result};

/// Default trusted IAM issuers - used as fallback if env var is not set
const DEFAULT_TRUSTED_IAM_ISSUERS: &[&str] = &[
    "did:key:GlMY_1zkc0i11O-wMBWbSiUfIkZiXzFLlAQ89pdfyBA",
    "did:ethr:0xabczyx",
];

/// How far `issuanceDate` may be ahead of the scorer's clock. `ssi` rejects any
/// future `issuanceDate` as premature. The Python scorer's didkit accepts one,
/// so without this an IAM clock running ahead would make the two scorers disagree.
const ISSUANCE_CLOCK_SKEW_SECS: i64 = 300;

/// Cached trusted IAM issuers loaded from environment variable
static TRUSTED_IAM_ISSUERS: OnceLock<Vec<String>> = OnceLock::new();

/// Get the list of trusted IAM issuers from environment variable or defaults
fn get_trusted_issuers() -> &'static Vec<String> {
    TRUSTED_IAM_ISSUERS.get_or_init(|| {
        match std::env::var("TRUSTED_IAM_ISSUERS") {
            Ok(json_str) => {
                match serde_json::from_str::<Vec<String>>(&json_str) {
                    Ok(issuers) => {
                        info!("Loaded {} trusted IAM issuers from TRUSTED_IAM_ISSUERS env var", issuers.len());
                        issuers
                    }
                    Err(e) => {
                        warn!("Failed to parse TRUSTED_IAM_ISSUERS env var: {}. Using defaults.", e);
                        DEFAULT_TRUSTED_IAM_ISSUERS.iter().map(|s| s.to_string()).collect()
                    }
                }
            }
            Err(_) => {
                info!("TRUSTED_IAM_ISSUERS env var not set, using defaults");
                DEFAULT_TRUSTED_IAM_ISSUERS.iter().map(|s| s.to_string()).collect()
            }
        }
    })
}

/// Represents a validated credential
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidatedCredential {
    pub provider: String,
    pub credential: Value,
    pub nullifiers: Vec<String>,
    pub expires_at: DateTime<Utc>,
}

/// Validate a single credential
#[tracing::instrument(skip(credential), fields(address))]
pub async fn validate_credential(
    credential: &Value,
    address: &str,
) -> Result<Option<ValidatedCredential>> {
    validate_credential_with_issuers(credential, address, get_trusted_issuers()).await
}

/// `validate_credential` with the trusted issuers passed in, so tests do not
/// depend on the process-wide `TRUSTED_IAM_ISSUERS`.
async fn validate_credential_with_issuers(
    credential: &Value,
    address: &str,
    trusted_issuers: &[String],
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

    if !issuer.map(|i| trusted_issuers.iter().any(|t| t == i)).unwrap_or(false) {
        warn!("Untrusted issuer: {:?}", issuer);
        return Ok(None);
    }
    
    // Verify the credential signature
    if let Err(reason) = verify_signature(credential, None).await {
        warn!("Credential verification failed: {}", reason);
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

/// Verify the Data Integrity proof on a credential with `ssi`.
///
/// Matches the checks the Python scorer gets from didkit: the proof purpose is
/// `assertionMethod`, the proof's verification method belongs to the issuer, and
/// the signature is valid. `at` overrides the current time (tests only).
pub(crate) async fn verify_signature(
    credential: &Value,
    at: Option<DateTime<Utc>>,
) -> std::result::Result<(), String> {
    use ssi::claims::VerificationParameters;
    use ssi::dids::{AnyDidMethod, DIDResolver};

    let mut vc = credential.clone();
    let proof = vc
        .get_mut("proof")
        .and_then(|p| p.as_object_mut())
        .ok_or("missing proof")?;

    if proof.get("proofPurpose").and_then(|p| p.as_str()) != Some("assertionMethod") {
        return Err("proof purpose is not assertionMethod".into());
    }

    // `ssi` does not check that the verification method belongs to the issuer,
    // so a credential naming a trusted issuer but signed by any other key would
    // verify. The old didkit rejected that ("No applicable proof"). Check it here.
    let issuer = credential
        .get("issuer")
        .and_then(|i| i.as_str())
        .ok_or("missing issuer")?;
    let method = proof
        .get("verificationMethod")
        .and_then(|m| m.as_str())
        .ok_or("missing verificationMethod")?;
    match method.split_once('#') {
        Some((did, _)) if did == issuer => {}
        _ => return Err(format!("verification method {method} does not belong to issuer {issuer}")),
    }

    // Passport signs with the older EthereumEip712Signature2021 layout, which puts
    // the EIP-712 types under `eip712Domain`. `ssi` reads them from `eip712`.
    // The key is not part of the signed message, so renaming it is safe.
    if let Some(domain) = proof.remove("eip712Domain") {
        proof.insert("eip712".into(), domain);
    }

    let text = serde_json::to_string(&vc).map_err(|e| e.to_string())?;
    let vc = ssi::claims::vc::v1::data_integrity::any_credential_from_json_str(&text)
        .map_err(|e| format!("invalid credential format: {e}"))?;

    // Verify at `issuanceDate` when it is only slightly ahead of now (clock skew).
    // `ssi` checks no other date against this time; validate_credential checks expiry itself.
    let now = at.unwrap_or_else(Utc::now);
    let issued = credential
        .get("issuanceDate")
        .and_then(|d| d.as_str())
        .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
        .map(|d| d.with_timezone(&Utc));
    let verify_at = match issued {
        Some(t) if t > now && (t - now).num_seconds() <= ISSUANCE_CLOCK_SKEW_SECS => t,
        _ => now,
    };
    let params = VerificationParameters::from_resolver(AnyDidMethod::default().into_vm_resolver())
        .with_date_time(verify_at);

    // Box the future behind `dyn` to erase its deeply nested type. Without it,
    // the axum handler's `Send` check overflows the compiler's recursion limit.
    let verification: std::pin::Pin<Box<dyn std::future::Future<Output = _> + Send + '_>> =
        Box::pin(vc.verify(&params));
    match verification.await {
        Ok(Ok(())) => Ok(()),
        Ok(Err(e)) => Err(format!("{e:?}")),
        Err(e) => Err(e.to_string()),
    }
}

/// Validate multiple credentials
#[tracing::instrument(skip(credentials), fields(count = credentials.len(), address = %address))]
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
            "issuer": "did:key:GlMY_1zkc0i11O-wMBWbSiUfIkZiXzFLlAQ89pdfyBA"
        });

        let result = validate_credential(&credential, "0x123").await.unwrap();
        assert!(result.is_none(), "Expired credential should return None");
    }

    fn fixtures() -> Value {
        serde_json::from_str(include_str!("../../tests/fixtures/eip712_credentials.json")).unwrap()
    }

    #[tokio::test]
    async fn test_signature_valid_didkit_signed() {
        // Signed by didkit 0.6 (the library the Python scorer and the IAM use)
        for c in fixtures()["didkit_signed"].as_array().unwrap() {
            assert_eq!(verify_signature(c, None).await, Ok(()));
        }
    }

    #[tokio::test]
    async fn test_signature_valid_ssi_signed() {
        let f = fixtures();
        assert_eq!(verify_signature(&f["ssi_signed"], None).await, Ok(()));
    }

    #[tokio::test]
    async fn test_signature_rejects_tampered_fields() {
        let f = fixtures();
        let c = &f["didkit_signed"][0];
        for (path, value) in [
            (vec!["credentialSubject", "provider"], json!("Biometrics")),
            (vec!["credentialSubject", "id"], json!("did:pkh:eip155:1:0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")),
            (vec!["credentialSubject", "nullifiers"], json!(["v0:other"])),
            (vec!["expirationDate"], json!("2199-01-01T00:00:00Z")),
        ] {
            let mut t = c.clone();
            let mut node = &mut t;
            for key in &path[..path.len() - 1] {
                node = node.get_mut(*key).unwrap();
            }
            node[path[path.len() - 1]] = value;
            assert!(verify_signature(&t, None).await.is_err(), "tampered {:?} must fail", path);
        }
    }

    #[tokio::test]
    async fn test_signature_rejects_key_not_owned_by_issuer() {
        // Names the trusted issuer, signed by an unrelated key
        let f = fixtures();
        let err = verify_signature(&f["forged_issuer"], None).await.unwrap_err();
        assert!(err.contains("does not belong to issuer"), "{err}");
    }

    #[tokio::test]
    async fn test_signature_rejects_wrong_proof_purpose() {
        let mut c = fixtures()["didkit_signed"][0].clone();
        c["proof"]["proofPurpose"] = json!("authentication");
        assert!(verify_signature(&c, None).await.is_err());
    }

    #[tokio::test]
    async fn test_signature_rejects_missing_proof() {
        let mut c = fixtures()["didkit_signed"][0].clone();
        c.as_object_mut().unwrap().remove("proof");
        assert!(verify_signature(&c, None).await.is_err());
    }

    #[tokio::test]
    async fn test_signature_issuance_clock_skew() {
        let c = &fixtures()["didkit_signed"][0];
        let issued = DateTime::parse_from_rfc3339(c["issuanceDate"].as_str().unwrap())
            .unwrap()
            .with_timezone(&Utc);
        let ahead = |secs| Some(issued - chrono::Duration::seconds(secs));
        // Issued slightly in the future: accepted
        assert_eq!(verify_signature(c, ahead(30)).await, Ok(()));
        assert_eq!(verify_signature(c, ahead(ISSUANCE_CLOCK_SKEW_SECS)).await, Ok(()));
        // Beyond the tolerance: still premature
        let err = verify_signature(c, ahead(ISSUANCE_CLOCK_SKEW_SECS + 1)).await.unwrap_err();
        assert!(err.contains("Premature"), "{err}");
    }

    #[tokio::test]
    async fn test_validate_credential_end_to_end() {
        let f = fixtures();
        let c = &f["didkit_signed"][0];
        let trusted = vec![c["issuer"].as_str().unwrap().to_string()];
        let address = format!("0x{}", "a".repeat(40));
        let valid = validate_credential_with_issuers(c, &address, &trusted).await.unwrap();
        assert!(valid.is_some());

        // The same credential is rejected when its issuer is not trusted
        let other = vec!["did:ethr:0x0000000000000000000000000000000000000000".to_string()];
        let rejected = validate_credential_with_issuers(c, &address, &other).await.unwrap();
        assert!(rejected.is_none());
    }
}
