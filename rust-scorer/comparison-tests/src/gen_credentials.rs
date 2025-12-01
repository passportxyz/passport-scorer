//! Generate test credentials with EthereumEip712Signature2021 signatures
//!
//! This matches the production credential format used by Passport.

use anyhow::{Context, Result};
use chrono::{Duration, Utc};
use didkit::ssi::jwk::{JWK, Base64urlUInt, ECParams, Params};
use didkit::ssi::vc::{Credential, LinkedDataProofOptions, ProofPurpose, URI};
use didkit::ssi::ldp::{ProofSuiteType, eip712::{ProofInfo, TypesOrURI, EIP712Value}};
use didkit::ssi::jsonld::ContextLoader;
use didkit::{DID_METHODS, VerifiableCredential};
use serde_json::{json, Value};
use sqlx::postgres::PgPoolOptions;
use std::env;
use std::path::Path;

/// EIP-712 type definitions for stamp credentials (matches TypeScript signingDocuments.ts)
fn stamp_credential_eip712_types() -> Value {
    json!({
        "EIP712Domain": [
            { "type": "string", "name": "name" }
        ],
        "NullifiersContext": [
            { "type": "string", "name": "@container" },
            { "type": "string", "name": "@type" }
        ],
        "@context": [
            { "type": "NullifiersContext", "name": "nullifiers" },
            { "type": "string", "name": "provider" }
        ],
        "Document": [
            { "type": "string[]", "name": "@context" },
            { "type": "CredentialSubject", "name": "credentialSubject" },
            { "type": "string", "name": "expirationDate" },
            { "type": "string", "name": "issuanceDate" },
            { "type": "string", "name": "issuer" },
            { "type": "Proof", "name": "proof" },
            { "type": "string[]", "name": "type" }
        ],
        "Proof": [
            { "type": "string", "name": "@context" },
            { "type": "string", "name": "created" },
            { "type": "string", "name": "proofPurpose" },
            { "type": "string", "name": "type" },
            { "type": "string", "name": "verificationMethod" }
        ],
        "CredentialSubject": [
            { "type": "@context", "name": "@context" },
            { "type": "string[]", "name": "nullifiers" },
            { "type": "string", "name": "id" },
            { "type": "string", "name": "provider" }
        ]
    })
}

/// Get the hardcoded test secp256k1 Ethereum key
/// This ensures the issuer DID stays constant across test runs, so TRUSTED_IAM_ISSUERS
/// doesn't need to be updated in .env.development each time credentials are regenerated.
fn get_test_ethereum_key() -> Result<JWK> {
    use k256::ecdsa::SigningKey;
    use k256::elliptic_curve::sec1::ToEncodedPoint;

    // Hardcoded test private key (32 bytes)
    // This is a randomly generated key that is ONLY for local testing - not used in production
    // Corresponding DID: did:ethr:0x018d103c154748e8d5a1d7658185125175457f84
    let d: [u8; 32] = [
        0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0,
        0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88,
        0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff, 0x00, 0x11,
        0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99,
    ];

    // Use k256 to derive the public key
    let signing_key = SigningKey::from_bytes((&d).into())
        .context("Failed to create signing key")?;
    let verifying_key = signing_key.verifying_key();
    let point = verifying_key.to_encoded_point(false);

    let x = point.x().ok_or_else(|| anyhow::anyhow!("Missing x coordinate"))?;
    let y = point.y().ok_or_else(|| anyhow::anyhow!("Missing y coordinate"))?;

    let jwk = JWK {
        params: Params::EC(ECParams {
            curve: Some("secp256k1".to_string()),
            x_coordinate: Some(Base64urlUInt(x.to_vec())),
            y_coordinate: Some(Base64urlUInt(y.to_vec())),
            ecc_private_key: Some(Base64urlUInt(d.to_vec())),
        }),
        public_key_use: None,
        key_operations: None,
        algorithm: None,
        key_id: None,
        x509_url: None,
        x509_certificate_chain: None,
        x509_thumbprint_sha1: None,
        x509_thumbprint_sha256: None,
    };

    Ok(jwk)
}

/// Create a signed verifiable credential with EthereumEip712Signature2021
async fn create_signed_credential(
    address: &str,
    provider: &str,
    key: &JWK,
    issuer_did: &str,
    verification_method: &str,
) -> Result<Value> {
    let now = Utc::now();
    let expiration = now + Duration::days(90);

    // Create the credential - matching production format exactly
    let credential_json = json!({
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://w3id.org/vc/status-list/2021/v1"
        ],
        "type": ["VerifiableCredential"],
        "issuer": issuer_did,
        "issuanceDate": now.format("%Y-%m-%dT%H:%M:%SZ").to_string(),
        "expirationDate": expiration.format("%Y-%m-%dT%H:%M:%SZ").to_string(),
        "credentialSubject": {
            "id": format!("did:pkh:eip155:1:{}", address.to_lowercase()),
            "@context": {
                "provider": "https://schema.org/Text",
                "nullifiers": {
                    "@type": "https://schema.org/Text",
                    "@container": "@list"
                }
            },
            "provider": provider,
            "nullifiers": [format!("v0:{}:{}:test-nullifier", provider, address.to_lowercase())]
        }
    });

    // Use VerifiableCredential::from_json_unsigned like the FFI does
    // This is what TypeScript DIDKit.issueCredential does internally
    let credential_str = serde_json::to_string(&credential_json)?;
    let mut credential = VerifiableCredential::from_json_unsigned(&credential_str)
        .context("Failed to parse credential")?;

    // Create EIP-712 proof options with the signing document structure
    // This matches what the TypeScript/Python FFI does
    let types: didkit::ssi::ldp::eip712::Types =
        serde_json::from_value(stamp_credential_eip712_types())?;

    let proof_info = ProofInfo {
        types_or_uri: TypesOrURI::Object(types),
        primary_type: "Document".to_string(),
        domain: EIP712Value::Struct([(
            "name".to_string(),
            EIP712Value::String("VerifiableCredential".to_string())
        )].iter().cloned().collect()),
    };

    let proof_options = LinkedDataProofOptions {
        proof_purpose: Some(ProofPurpose::AssertionMethod),
        verification_method: Some(URI::String(verification_method.to_string())),
        type_: Some(ProofSuiteType::EthereumEip712Signature2021),
        eip712_domain: Some(proof_info),
        ..Default::default()
    };

    // Sign the credential - matching the FFI flow
    let resolver = DID_METHODS.to_resolver();
    let mut context_loader = ContextLoader::default();

    let proof = credential
        .generate_proof(key, &proof_options, &*resolver, &mut context_loader)
        .await
        .context("Failed to generate proof")?;

    credential.add_proof(proof);

    // Convert back to JSON
    let signed = serde_json::to_value(&credential)?;
    Ok(signed)
}

#[tokio::main]
async fn main() -> Result<()> {
    println!("\n=== Generating EthereumEip712Signature2021 Test Credentials ===\n");

    // Load environment
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .context("Failed to find project root")?;

    let env_file = project_root.join(".env.development");
    if env_file.exists() {
        dotenvy::from_path_override(&env_file)?;
        println!("Loaded environment from .env.development");
    }

    // Connect to database
    let database_url = env::var("DATABASE_URL")
        .context("DATABASE_URL not set")?;

    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
        .context("Failed to connect to database")?;

    println!("Connected to database");

    // Get hardcoded test Ethereum key for signing
    let key = get_test_ethereum_key()?;

    // Get issuer DID and verification method using didkit's DID methods
    let did_method = DID_METHODS.get("ethr")
        .ok_or_else(|| anyhow::anyhow!("ethr DID method not found"))?;

    let issuer_did = did_method.generate(&didkit::Source::Key(&key))
        .ok_or_else(|| anyhow::anyhow!("Failed to generate DID"))?;

    let verification_method = didkit::ssi::vc::get_verification_method(&issuer_did, DID_METHODS.to_resolver())
        .await
        .ok_or_else(|| anyhow::anyhow!("Failed to get verification method"))?;

    println!("Issuer DID: {}", issuer_did);
    println!("Verification method: {}", verification_method);

    // Test address
    let test_address = format!("0x{}", "a".repeat(40));

    // Providers with weights that exceed threshold
    let providers = vec!["Google", "Twitter", "Github"];

    // Clear existing stamps
    let deleted = sqlx::query("DELETE FROM ceramic_cache_ceramiccache WHERE address = $1")
        .bind(&test_address.to_lowercase())
        .execute(&pool)
        .await?;
    println!("Cleared {} existing stamps for {}", deleted.rows_affected(), test_address);

    // Create signed credentials
    let mut credentials = Vec::new();
    for provider in &providers {
        let credential = create_signed_credential(
            &test_address,
            provider,
            &key,
            &issuer_did,
            &verification_method,
        )
        .await
        .with_context(|| format!("Failed to create credential for {}", provider))?;

        // Extract proof_value from the signed credential
        let proof_value = credential.get("proof")
            .and_then(|p| p.get("proofValue"))
            .and_then(|pv| pv.as_str())
            .unwrap_or("");

        // Insert into ceramic_cache_ceramiccache
        // type: 1 = V1, matching Django's IntegerChoices
        // compose_db_*: empty strings for test data
        sqlx::query(
            r#"
            INSERT INTO ceramic_cache_ceramiccache (
                address, provider, stamp, type, updated_at,
                compose_db_save_status, compose_db_stream_id, proof_value
            )
            VALUES ($1, $2, $3, 1, NOW(), '', '', $4)
            "#
        )
        .bind(&test_address.to_lowercase())
        .bind(*provider)
        .bind(&credential)
        .bind(proof_value)
        .execute(&pool)
        .await
        .with_context(|| format!("Failed to insert {} credential", provider))?;

        println!("Created signed credential for {}", provider);
        credentials.push(credential);
    }

    // Verify credentials
    println!("\nVerifying credentials...");
    for (i, credential) in credentials.iter().enumerate() {
        // Parse the credential
        let vc: Credential = serde_json::from_value(credential.clone())
            .context("Failed to parse credential for verification")?;

        // Set up verification options
        let proof_options = LinkedDataProofOptions {
            proof_purpose: Some(ProofPurpose::AssertionMethod),
            ..Default::default()
        };

        // Verify the credential
        let resolver = DID_METHODS.to_resolver();
        let mut context_loader = ContextLoader::default();
        let result = vc.verify(Some(proof_options), &*resolver, &mut context_loader).await;

        if result.errors.is_empty() {
            println!("  {}: VALID", providers[i]);
        } else {
            println!("  {}: INVALID - {:?}", providers[i], result.errors);
        }
    }

    // Get or create API key
    let api_key = get_or_create_api_key(&pool).await?;

    // Save test config
    let config = json!({
        "test_address": test_address.to_lowercase(),
        "scorer_id": 1,
        "api_key": api_key,
        "issuer_did": issuer_did,
        "providers": providers,
        "expected_score_above": 2.5,
        "credentials": credentials
    });

    let config_path = project_root
        .join("rust-scorer")
        .join("comparison-tests")
        .join("test_config.json");

    std::fs::write(&config_path, serde_json::to_string_pretty(&config)?)?;

    println!("\n=== Test Configuration ===");
    println!("Test address: {}", test_address);
    println!("Scorer ID: 1");
    println!("API Key: {}", api_key);
    println!("Issuer DID: {}", issuer_did);
    println!("Config saved to: {}", config_path.display());

    println!("\n=== IMPORTANT ===");
    println!("Add this DID to TRUSTED_IAM_ISSUERS in .env.development:");
    println!("TRUSTED_IAM_ISSUERS='[\"{}\"]'", issuer_did);

    Ok(())
}

async fn get_or_create_api_key(pool: &sqlx::PgPool) -> Result<String> {
    // Check if we have existing config with API key
    let config_path = Path::new(env!("CARGO_MANIFEST_DIR")).join("test_config.json");
    if config_path.exists() {
        let config: Value = serde_json::from_str(&std::fs::read_to_string(&config_path)?)?;
        if let Some(key) = config.get("api_key").and_then(|k| k.as_str()) {
            // Verify key still exists
            let prefix = &key[..8];
            let exists: Option<(String,)> = sqlx::query_as(
                "SELECT id FROM account_accountapikey WHERE prefix = $1 AND revoked = false"
            )
            .bind(prefix)
            .fetch_optional(pool)
            .await?;

            if exists.is_some() {
                return Ok(key.to_string());
            }
        }
    }

    // Need to create a new API key - this requires Python since it uses Django's password hasher
    println!("\nNote: Using existing API key from config or run create_test_credentials.py for new key");

    // For now, return a placeholder - the Python script should be run first
    Err(anyhow::anyhow!(
        "No valid API key found. Run 'poetry run python ../dev-setup/create_test_credentials.py' first to create one, \
         or ensure test_config.json has a valid api_key"
    ))
}
