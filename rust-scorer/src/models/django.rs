use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::FromRow;
use std::collections::HashMap;

/// Django registry_passport table
#[derive(Debug, Clone, FromRow)]
pub struct DjangoPassport {
    pub id: i64,
    pub address: String,
    pub community_id: i64,
}

/// Django registry_score table fields
#[derive(Debug, Clone)]
pub struct DjangoScoreFields {
    pub score: Decimal,
    pub status: String,
    pub last_score_timestamp: DateTime<Utc>,
    pub expiration_date: Option<DateTime<Utc>>,
    pub error: Option<String>,
    pub evidence: Value,
    pub stamp_scores: Value,
    pub stamps: HashMap<String, DjangoStampScore>,
}

/// Individual stamp score in Django format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DjangoStampScore {
    pub score: String,
    pub dedup: bool,
    pub expiration_date: Option<String>,
}

/// Django registry_stamp table
#[derive(Debug, Clone, FromRow)]
pub struct DjangoStamp {
    pub id: i64,
    pub passport_id: i64,
    pub provider: String,
    pub credential: Value,
}

/// Django registry_hashscorerlink table
#[derive(Debug, Clone, FromRow)]
pub struct DjangoHashScorerLink {
    pub id: i64,
    pub hash: String,
    pub address: String,
    pub community_id: i64,
    pub expires_at: DateTime<Utc>,
}

/// Django registry_event table
#[derive(Debug, Clone)]
pub struct DjangoEvent {
    pub action: String,
    pub address: String,
    pub data: Value,
    pub community_id: i64,
    pub created_at: DateTime<Utc>,
}

/// Django ceramic_cache table
#[derive(Debug, Clone, FromRow)]
pub struct DjangoCeramicCache {
    pub id: i64,
    pub address: String,
    pub provider: String,
    pub stamp: Value,
    pub deleted_at: Option<DateTime<Utc>>,
    pub created_at: Option<DateTime<Utc>>,  // Nullable with auto_now_add
    pub updated_at: Option<DateTime<Utc>>,  // Nullable with auto_now
    pub stamp_type: String,  // 'V1' or 'V2' (only V1 used)
}

/// Django account_community table
#[derive(Debug, Clone, FromRow)]
pub struct DjangoCommunity {
    pub id: i64,
    pub name: String,
    pub description: String,
    pub human_points_program: bool,
    pub created_at: Option<DateTime<Utc>>,  // nullable in Django
}

/// Django scorer_weighted_binaryweightedscorer table
#[derive(Debug, Clone, FromRow)]
pub struct DjangoBinaryWeightedScorer {
    pub scorer_ptr_id: i64,
    pub weights: Value,
    pub threshold: Decimal,
}

/// Django account_customization table
#[derive(Debug, Clone, FromRow)]
pub struct DjangoCustomization {
    pub id: i64,
    pub scorer_id: i64,  // OneToOneField to Community
    // Note: weights field doesn't exist in account_customization table
    // This table is for UI customization, not scorer weights
}

/// Django account_accountapikey table
#[derive(Debug, Clone, FromRow)]
pub struct DjangoApiKey {
    pub id: String,
    pub prefix: String,
    pub hashed_key: String,
    pub hashed_key_sha256: Option<String>,  // SHA-256 hash for fast verification
    pub account_id: i64,
    pub name: String,
    pub revoked: bool,
    pub submit_passports: bool,
    pub read_scores: bool,
    pub create_scorers: bool,
    pub created: DateTime<Utc>,
    pub expiry_date: Option<DateTime<Utc>>,
    pub embed_rate_limit: Option<String>,  // Rate limit tier for embed endpoints
}

/// Django registry_humanpoints table (Human Points)
#[derive(Debug, Clone)]
pub struct DjangoHumanPoints {
    pub address: String,
    pub action: String,
    pub chain_id: Option<i32>,
    pub provider: Option<String>,
    pub tx_hash: Option<String>,
    pub created_at: DateTime<Utc>,
}

/// Django registry_humanpointscommunityqualifiedusers table
#[derive(Debug, Clone)]
pub struct DjangoHumanPointsQualifiedUser {
    pub address: String,
    pub community_id: i64,
    pub created_at: DateTime<Utc>,
}