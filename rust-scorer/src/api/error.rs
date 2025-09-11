use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;
use std::fmt;

#[derive(Debug)]
pub enum ApiError {
    BadRequest(String),
    Unauthorized(String),
    NotFound(String),
    Internal(String),
    Database(String),
    Validation(String),
}

impl fmt::Display for ApiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ApiError::BadRequest(msg) => write!(f, "Bad request: {}", msg),
            ApiError::Unauthorized(msg) => write!(f, "Unauthorized: {}", msg),
            ApiError::NotFound(msg) => write!(f, "Not found: {}", msg),
            ApiError::Internal(msg) => write!(f, "Internal error: {}", msg),
            ApiError::Database(msg) => write!(f, "Database error: {}", msg),
            ApiError::Validation(msg) => write!(f, "Validation error: {}", msg),
        }
    }
}

impl std::error::Error for ApiError {}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
    message: String,
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, error_type, message) = match self {
            ApiError::BadRequest(msg) => (StatusCode::BAD_REQUEST, "bad_request", msg),
            ApiError::Unauthorized(msg) => (StatusCode::UNAUTHORIZED, "unauthorized", msg),
            ApiError::NotFound(msg) => (StatusCode::NOT_FOUND, "not_found", msg),
            ApiError::Internal(msg) => (StatusCode::INTERNAL_SERVER_ERROR, "internal_error", msg),
            ApiError::Database(msg) => (StatusCode::INTERNAL_SERVER_ERROR, "database_error", msg),
            ApiError::Validation(msg) => (StatusCode::BAD_REQUEST, "validation_error", msg),
        };

        let body = Json(ErrorResponse {
            error: error_type.to_string(),
            message,
        });

        (status, body).into_response()
    }
}

impl From<sqlx::Error> for ApiError {
    fn from(err: sqlx::Error) -> Self {
        ApiError::Database(err.to_string())
    }
}

impl From<serde_json::Error> for ApiError {
    fn from(err: serde_json::Error) -> Self {
        ApiError::Internal(format!("JSON error: {}", err))
    }
}

impl From<std::env::VarError> for ApiError {
    fn from(err: std::env::VarError) -> Self {
        ApiError::Internal(format!("Environment variable error: {}", err))
    }
}

impl From<crate::db::DatabaseError> for ApiError {
    fn from(err: crate::db::DatabaseError) -> Self {
        match err {
            crate::db::DatabaseError::NotFound(msg) => ApiError::NotFound(msg),
            crate::db::DatabaseError::IntegrityError(msg) => ApiError::Database(msg),
            crate::db::DatabaseError::ConnectionError(msg) => ApiError::Database(msg),
            crate::db::DatabaseError::TransactionError(msg) => ApiError::Database(msg),
            crate::db::DatabaseError::QueryError(e) => ApiError::Database(e.to_string()),
            crate::db::DatabaseError::SerializationError(e) => ApiError::Internal(e.to_string()),
            crate::db::DatabaseError::InvalidData(msg) => ApiError::Validation(msg),
            crate::db::DatabaseError::Unauthorized(msg) => ApiError::Unauthorized(msg),
            crate::db::DatabaseError::RetryLimitExceeded { attempts } => {
                ApiError::Database(format!("Retry limit exceeded after {} attempts", attempts))
            }
        }
    }
}

impl From<anyhow::Error> for ApiError {
    fn from(err: anyhow::Error) -> Self {
        ApiError::Internal(err.to_string())
    }
}

pub type ApiResult<T> = Result<T, ApiError>;