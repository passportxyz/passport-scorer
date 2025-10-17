use thiserror::Error;

#[derive(Error, Debug)]
pub enum DatabaseError {
    #[error("Database connection error: {0}")]
    ConnectionError(String),
    
    #[error("Query execution error: {0}")]
    QueryError(#[from] sqlx::Error),
    
    #[error("Transaction error: {0}")]
    TransactionError(String),
    
    #[error("Integrity constraint violation: {0}")]
    IntegrityError(String),
    
    #[error("Record not found: {0}")]
    NotFound(String),
    
    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),
    
    #[error("Invalid data: {0}")]
    InvalidData(String),
    
    #[error("Unauthorized: {0}")]
    Unauthorized(String),
    
    #[error("Retry limit exceeded after {attempts} attempts")]
    RetryLimitExceeded { attempts: u8 },
}

impl DatabaseError {
    /// Check if this is an integrity constraint violation that should trigger a retry
    pub fn is_integrity_error(&self) -> bool {
        match self {
            Self::IntegrityError(_) => true,
            Self::QueryError(e) => {
                // Check SQLx error for integrity constraint violations
                if let Some(db_error) = e.as_database_error() {
                    // PostgreSQL integrity constraint violation codes
                    matches!(db_error.code().as_deref(), 
                        Some("23505") | // unique_violation
                        Some("23503") | // foreign_key_violation
                        Some("23502")   // not_null_violation
                    )
                } else {
                    false
                }
            }
            _ => false,
        }
    }
    
    /// Check if this error is retryable
    pub fn is_retryable(&self) -> bool {
        match self {
            Self::IntegrityError(_) => true,
            Self::QueryError(e) => {
                // Check for transient errors like deadlocks or serialization failures
                if let Some(db_error) = e.as_database_error() {
                    matches!(db_error.code().as_deref(),
                        Some("40001") | // serialization_failure
                        Some("40P01") | // deadlock_detected
                        Some("23505")   // unique_violation (for LIFO retry)
                    )
                } else {
                    false
                }
            }
            Self::ConnectionError(_) => true,
            _ => false,
        }
    }
}

pub type Result<T> = std::result::Result<T, DatabaseError>;