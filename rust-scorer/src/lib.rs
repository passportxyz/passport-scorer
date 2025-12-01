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
};