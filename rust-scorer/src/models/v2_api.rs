use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
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