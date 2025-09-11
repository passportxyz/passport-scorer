pub mod models;
pub mod db;
pub mod auth;
pub mod dedup;
pub mod scoring;
pub mod human_points;
pub mod api;

// Re-export commonly used types
pub use models::{
    ScoringResult, StampData, ValidStamp, V2ScoreResponse,
    DjangoScoreFields, DjangoPassport, DjangoStamp,
};

pub use db::{
    init_pool, get_pool, health_check, with_retry,
    DatabaseError,
};

pub use dedup::{lifo_dedup, LifoResult};

pub use scoring::{calculate_score, build_scoring_result, ScorerConfig};

pub use human_points::{
    process_human_points, 
    HumanPointsConfig,
    get_user_points_data,
    get_possible_points_data,
};