// Domain layer - shared business logic with no HTTP concerns
// These modules contain pure business logic that can be used by both
// internal and external API handlers

pub mod scoring;
pub mod weights;
pub mod stamps;
pub mod bans;
pub mod stakes;
pub mod cgrants;
pub mod allow_list;
pub mod dedup;
pub mod human_points;

// Domain error type - no HTTP concerns
#[derive(Debug, thiserror::Error)]
pub enum DomainError {
    #[error("Database error: {0}")]
    Database(String),

    #[error("Validation error: {0}")]
    Validation(String),

    #[error("Not found: {0}")]
    NotFound(String),

    #[error("Internal error: {0}")]
    Internal(String),
}

impl From<sqlx::Error> for DomainError {
    fn from(e: sqlx::Error) -> Self {
        match e {
            sqlx::Error::RowNotFound => DomainError::NotFound("Resource not found".to_string()),
            _ => DomainError::Database(e.to_string()),
        }
    }
}

// Re-export commonly used types and functions
pub use scoring::{calculate_score, build_scoring_result, calculate_score_for_address};
pub use weights::get_scorer_weights;
pub use dedup::lifo_dedup;
pub use human_points::{process_human_points, get_user_points_data, get_possible_points_data};