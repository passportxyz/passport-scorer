use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use rust_decimal::prelude::ToPrimitive;
use serde_json::json;
use std::collections::HashMap;

use super::{
    DjangoScoreFields, DjangoStampScore, ScoringEvent, ScoringResult,
    V2ScoreResponse, V2StampScoreResponse, format_decimal_5,
};

impl ScoringResult {
    /// Convert to V2 API response format
    pub fn to_v2_response(&self) -> V2ScoreResponse {
        let mut stamps = HashMap::new();
        
        // Add valid stamps with their weights
        for stamp in &self.valid_stamps {
            stamps.insert(
                stamp.provider.clone(),
                V2StampScoreResponse {
                    score: format_decimal_5(stamp.weight),
                    dedup: false,
                    expiration_date: Some(stamp.expires_at.to_rfc3339()),
                },
            );
        }
        
        // Add deduped stamps with zero score
        for stamp in &self.deduped_stamps {
            stamps.insert(
                stamp.provider.clone(),
                V2StampScoreResponse {
                    score: "0.00000".to_string(),
                    dedup: true,
                    expiration_date: Some(stamp.expires_at.to_rfc3339()),
                },
            );
        }
        
        V2ScoreResponse {
            address: self.address.clone(),
            score: Some(format_decimal_5(self.binary_score)),
            passing_score: self.binary_score >= Decimal::from(1),
            threshold: format_decimal_5(self.threshold),
            last_score_timestamp: Some(self.timestamp.to_rfc3339()),
            expiration_timestamp: self.expires_at.map(|t| t.to_rfc3339()),
            error: None,
            stamps,
            points_data: None,
            possible_points_data: None,
        }
    }
    
    /// Convert to Django database fields
    pub fn to_django_score_fields(&self) -> DjangoScoreFields {
        let mut stamp_scores = HashMap::new();
        
        // Only valid stamps go in stamp_scores (for scoring logic)
        for stamp in &self.valid_stamps {
            stamp_scores.insert(stamp.provider.clone(), stamp.weight.to_f64().unwrap());
        }
        
        // Build stamps dict for Django (includes both valid and deduped)
        let mut stamps = HashMap::new();
        
        for stamp in &self.valid_stamps {
            stamps.insert(
                stamp.provider.clone(),
                DjangoStampScore {
                    score: format_decimal_5(stamp.weight),
                    dedup: false,
                    expiration_date: Some(stamp.expires_at.to_rfc3339()),
                },
            );
        }
        
        for stamp in &self.deduped_stamps {
            stamps.insert(
                stamp.provider.clone(),
                DjangoStampScore {
                    score: "0.00000".to_string(),
                    dedup: true,
                    expiration_date: Some(stamp.expires_at.to_rfc3339()),
                },
            );
        }
        
        DjangoScoreFields {
            score: self.binary_score,
            status: "DONE".to_string(),
            last_score_timestamp: self.timestamp,
            expiration_date: self.expires_at,
            error: None,
            evidence: json!({
                "type": "ThresholdScoreCheck",
                "success": self.binary_score == Decimal::from(1),
                "rawScore": self.raw_score.to_string(),
                "threshold": self.threshold.to_string()
            }),
            stamp_scores: json!(stamp_scores),
            stamps,
        }
    }
    
    /// Future: Convert to single event row for new architecture
    pub fn to_scoring_event(&self) -> ScoringEvent {
        ScoringEvent {
            address: self.address.clone(),
            community_id: self.community_id,
            score: self.binary_score,
            threshold: self.threshold,
            raw_score: self.raw_score,
            stamps_snapshot: json!({
                "valid": &self.valid_stamps,
                "deduped": &self.deduped_stamps,
            }),
            weights: self.valid_stamps.iter()
                .map(|s| (s.provider.clone(), s.weight))
                .collect(),
            expires_at: self.expires_at,
            timestamp: self.timestamp,
            scorer_version: env!("CARGO_PKG_VERSION").to_string(),
        }
    }
}

/// Create SCORE_UPDATE event data matching Django's serializers.serialize() format
pub fn create_score_update_event_data(
    score_id: i32,
    passport_id: i32,
    score: Decimal,
    last_score_timestamp: DateTime<Utc>,
    evidence: serde_json::Value,
    stamp_scores: serde_json::Value,
    stamps: &HashMap<String, DjangoStampScore>,
    expiration_date: Option<DateTime<Utc>>,
) -> serde_json::Value {
    json!([{
        "model": "registry.score",
        "pk": score_id,
        "fields": {
            "passport": passport_id,
            "score": score.to_string(),
            "last_score_timestamp": last_score_timestamp.to_rfc3339(),
            "status": "DONE",
            "error": null,
            "evidence": evidence,
            "stamp_scores": stamp_scores,
            "stamps": stamps,
            "expiration_date": expiration_date.map(|d| d.to_rfc3339())
        }
    }])
}