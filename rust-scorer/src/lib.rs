pub mod models;
pub mod db;
pub mod auth;
pub mod api;
pub mod secrets;
pub mod domain;

// Re-export commonly used types
pub use models::{
    ScoringResult, StampData, ValidStamp, V2ScoreResponse,
    DjangoScoreFields, DjangoPassport, DjangoStamp,
};

pub use db::{
    init_pool, get_pool, health_check, with_retry,
    DatabaseError,
};

// Domain logic is now accessed through the domain module
pub use domain::{
    calculate_score_for_address,
    get_scorer_weights,
    lifo_dedup,
};

// Re-export LIFO dedup types for integration tests
pub use domain::dedup::LifoResult;

// Re-export human_points module for integration tests
// This combines types from models::human_points and domain::human_points
pub mod human_points {
    // Types from models
    pub use crate::models::human_points::{HumanPointsAction, STAMP_PROVIDER_TO_ACTION};
    // Types and functions from domain
    pub use crate::domain::human_points::{HumanPointsConfig, process_human_points, get_user_points_data, get_possible_points_data};
}