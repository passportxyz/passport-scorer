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

/// Main V2 API response structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct V2ScoreResponse {
    pub address: String,
    pub score: Option<String>,  // Formatted with 5 decimals
    pub passing_score: bool,
    pub threshold: String,  // Formatted with 5 decimals
    pub last_score_timestamp: Option<String>,
    pub expiration_timestamp: Option<String>,
    pub error: Option<String>,
    pub stamps: HashMap<String, V2StampScoreResponse>,
    // Optional fields for Human Points
    #[serde(skip_serializing_if = "Option::is_none")]
    pub points_data: Option<PointsData>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub possible_points_data: Option<PointsData>,
}

/// Human Points data structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PointsData {
    pub total_points: i32,
    pub is_eligible: bool,
    pub multiplier: f64,
    pub breakdown: HashMap<String, PointBreakdown>,
}

/// Individual point breakdown
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PointBreakdown {
    pub points: i32,
    pub chain_id: Option<i32>,
}

/// Format a decimal with 5 decimal places for API response
pub fn format_decimal_5(value: Decimal) -> String {
    format!("{:.5}", value)
}

/// Format a decimal as a percentage string
pub fn format_percentage(value: Decimal) -> String {
    format!("{:.2}%", value * Decimal::from(100))
}

impl V2ScoreResponse {
    /// Create an error response
    pub fn error(address: String, error_message: String) -> Self {
        Self {
            address,
            score: None,
            passing_score: false,
            threshold: "0.00000".to_string(),
            last_score_timestamp: None,
            expiration_timestamp: None,
            error: Some(error_message),
            stamps: HashMap::new(),
            points_data: None,
            possible_points_data: None,
        }
    }
}