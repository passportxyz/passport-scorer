use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// Individual stamp score in V2 API response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct V2StampScoreResponse {
    pub score: String,
    pub dedup: bool,
    pub expiration_date: Option<String>,
}

/// Main V2 API response structure - field order matches Python for exact compatibility
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct V2ScoreResponse {
    pub address: String,
    pub score: Option<String>,  // Formatted with 5 decimals
    pub passing_score: bool,
    pub last_score_timestamp: Option<String>,
    pub expiration_timestamp: Option<String>,
    pub threshold: String,  // Formatted with 5 decimals
    pub error: Option<String>,
    pub stamps: HashMap<String, V2StampScoreResponse>,
    pub points_data: Option<PointsData>,
    pub possible_points_data: Option<PointsData>,
}

/// Internal score response type alias - includes human points data when available
/// This matches Python's InternalV2ScoreResponse which extends V2ScoreResponse
pub type InternalV2ScoreResponse = V2ScoreResponse;

/// Human Points data structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PointsData {
    pub total_points: i32,
    pub is_eligible: bool,
    pub multiplier: i32,  // Django uses integer, not float
    pub breakdown: HashMap<String, i32>,  // Django uses flat integers, not nested objects
}

/// Format a decimal with 5 decimal places for API response
pub fn format_decimal_5(value: Decimal) -> String {
    format!("{:.5}", value)
}

/// Format a decimal as a percentage string
pub fn format_percentage(value: Decimal) -> String {
    format!("{:.2}%", value * Decimal::from(100))
}

/// Format a datetime to ISO 8601 with 6 decimal places for microseconds (Python compatibility)
pub fn format_datetime_python(dt: DateTime<Utc>) -> String {
    // Format with 6 decimal places for microseconds like Python does
    let base = dt.format("%Y-%m-%dT%H:%M:%S");
    let micros = dt.timestamp_subsec_micros();
    format!("{}.{:06}+00:00", base, micros)
}

impl V2ScoreResponse {
    /// Create an error response
    pub fn error(address: String, error_message: String) -> Self {
        Self {
            address,
            score: None,
            passing_score: false,
            last_score_timestamp: None,
            expiration_timestamp: None,
            threshold: "0.00000".to_string(),
            error: Some(error_message),
            stamps: HashMap::new(),
            points_data: None,
            possible_points_data: None,
        }
    }
}

/// Response for embed endpoints that return stamps + score
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GetStampsWithV2ScoreResponse {
    pub success: bool,
    pub stamps: Vec<CachedStampResponse>,
    pub score: V2ScoreResponse,
}

/// Internal response for ceramic-cache endpoints that includes stamps + score with human points
/// This matches Python's GetStampsWithInternalV2ScoreResponse
/// Since InternalV2ScoreResponse is a type alias of V2ScoreResponse, this is effectively the same
/// as GetStampsWithV2ScoreResponse, but we keep the naming for clarity
pub type GetStampsWithInternalV2ScoreResponse = GetStampsWithV2ScoreResponse;

/// Cached stamp response (subset of ceramic cache fields)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CachedStampResponse {
    pub id: i64,
    pub address: String,
    pub provider: String,
    pub stamp: Value,
}

/// API Key schema for embed validate endpoint
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountAPIKeySchema {
    pub embed_rate_limit: Option<String>,
}

/// Explicit deserializer for scorer_id that accepts both string and integer
/// and stores as String for explicit parsing in handler code
fn deserialize_scorer_id_to_string<'de, D>(deserializer: D) -> Result<String, D::Error>
where
    D: serde::Deserializer<'de>,
{
    use serde::de;

    struct ScorerIdVisitor;

    impl<'de> serde::de::Visitor<'de> for ScorerIdVisitor {
        type Value = String;

        fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
            formatter.write_str("an integer or string representing scorer_id")
        }

        fn visit_i64<E>(self, value: i64) -> Result<String, E>
        where
            E: de::Error,
        {
            Ok(value.to_string())
        }

        fn visit_u64<E>(self, value: u64) -> Result<String, E>
        where
            E: de::Error,
        {
            Ok(value.to_string())
        }

        fn visit_str<E>(self, value: &str) -> Result<String, E>
        where
            E: de::Error,
        {
            Ok(value.to_string())
        }
    }

    deserializer.deserialize_any(ScorerIdVisitor)
}

/// Payload for add stamps endpoint
/// Note: scorer_id accepts string or integer from clients (Python's Pydantic does the same)
/// but we store it as String and explicitly parse to i64 in the handler
#[derive(Debug, Clone, Deserialize)]
pub struct AddStampsPayload {
    /// Accepts "40" or 40 from JSON, stored as string for explicit conversion
    #[serde(deserialize_with = "deserialize_scorer_id_to_string")]
    pub scorer_id: String,
    pub stamps: Vec<Value>,
}

impl AddStampsPayload {
    /// Parse scorer_id to i64, returning error if invalid
    /// This is called explicitly in the handler to make the conversion visible
    pub fn parse_scorer_id(&self) -> Result<i64, String> {
        self.scorer_id
            .parse::<i64>()
            .map_err(|e| format!("Invalid scorer_id '{}': {}", self.scorer_id, e))
    }
}

/// Payload for ceramic-cache stamp operations (POST/PATCH/DELETE)
/// Matches Python's CacheStampPayload schema
#[derive(Debug, Clone, Deserialize)]
pub struct CacheStampPayload {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub address: Option<String>,
    pub provider: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stamp: Option<Value>,
}