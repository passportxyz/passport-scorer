use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// Clean internal model for stamp data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StampData {
    pub provider: String,
    pub credential: Value,
    pub nullifiers: Vec<String>,
    pub expires_at: DateTime<Utc>,
    pub weight: Decimal,
    pub was_deduped: bool,
}

/// Clean internal model for scoring results
#[derive(Debug)]
pub struct ScoringResult {
    pub address: String,
    pub community_id: i32,
    pub binary_score: Decimal,
    pub raw_score: Decimal,
    pub threshold: Decimal,
    pub valid_stamps: Vec<StampData>,
    pub deduped_stamps: Vec<StampData>,
    pub expires_at: Option<DateTime<Utc>>,
    pub timestamp: DateTime<Utc>,
}

/// Valid stamp after credential validation
#[derive(Debug, Clone)]
pub struct ValidStamp {
    pub provider: String,
    pub credential: Value,
    pub nullifiers: Vec<String>,
    pub expires_at: DateTime<Utc>,
}

/// Stamp info for clashing stamps
#[derive(Debug, Clone)]
pub struct StampInfo {
    pub nullifiers: Vec<String>,
    pub credential: Value,
    pub expires_at: DateTime<Utc>,  // Expiration from the clashing hash link
}

/// Future event-driven architecture model
#[derive(Debug, Serialize)]
pub struct ScoringEvent {
    pub address: String,
    pub community_id: i32,
    pub score: Decimal,
    pub threshold: Decimal,
    pub raw_score: Decimal,
    pub stamps_snapshot: Value,
    pub weights: HashMap<String, Decimal>,
    pub expires_at: Option<DateTime<Utc>>,
    pub timestamp: DateTime<Utc>,
    pub scorer_version: String,
}

/// Credential from ceramic cache
#[derive(Debug, Clone, Deserialize)]
pub struct CeramicCredential {
    #[serde(rename = "credentialSubject")]
    pub credential_subject: CredentialSubject,
    #[serde(rename = "expirationDate")]
    pub expiration_date: String,
    #[serde(rename = "issuanceDate")]
    pub issuance_date: String,
    pub issuer: String,
    pub proof: CredentialProof,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CredentialSubject {
    pub id: String,
    pub provider: String,
    pub nullifiers: Vec<String>,
    // Additional fields that might be present but we don't use
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CredentialProof {
    #[serde(rename = "proofValue")]
    pub proof_value: String,
    #[serde(rename = "type")]
    pub proof_type: String,
    // Additional proof fields
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
}