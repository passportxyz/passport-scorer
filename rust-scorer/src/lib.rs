pub mod models;
pub mod db;

// Re-export commonly used types
pub use models::{
    ScoringResult, StampData, ValidStamp, V2ScoreResponse,
    DjangoScoreFields, DjangoPassport, DjangoStamp,
};

pub use db::{
    init_pool, get_pool, health_check, with_retry,
    DatabaseError,
};