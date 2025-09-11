use axum::{
    routing::get,
    Router,
};
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use std::env;
use std::net::SocketAddr;
use std::time::Duration;
use tower_http::trace::TraceLayer;
use tracing::info;
use tracing_subscriber::{fmt, EnvFilter, prelude::*};

use crate::api::handler::score_address_handler;

pub fn init_tracing() {
    tracing_subscriber::registry()
        .with(
            fmt::layer()
                .json() // JSON format for CloudWatch
                .with_target(false)
                .with_current_span(true)
                .with_span_list(true)
        )
        .with(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info"))
        )
        .init();
}

pub async fn create_connection_pool() -> Result<PgPool, Box<dyn std::error::Error>> {
    let database_url = env::var("DATABASE_URL")
        .or_else(|_| env::var("RDS_PROXY_URL"))
        .expect("DATABASE_URL or RDS_PROXY_URL must be set");
    
    info!("Creating database connection pool");
    
    // Keep connection count low - RDS Proxy handles actual pooling
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .min_connections(1)
        .acquire_timeout(Duration::from_secs(3))
        .connect(&database_url)
        .await?;
    
    info!("Database connection pool created successfully");
    
    Ok(pool)
}

pub fn create_app(pool: PgPool) -> Router {
    Router::new()
        // Main v2 scoring endpoint
        .route(
            "/v2/stamps/:scorer_id/score/:address",
            get(score_address_handler),
        )
        // Health check endpoint
        .route("/health", get(health_check))
        // Add connection pool as state
        .with_state(pool)
        // Add tracing layer for observability
        .layer(TraceLayer::new_for_http())
}

async fn health_check() -> &'static str {
    "OK"
}

pub async fn run_server() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    init_tracing();
    
    info!("Starting Passport Scorer Rust server");
    
    // Create database connection pool
    let pool = create_connection_pool().await?;
    
    // Create the app
    let app = create_app(pool);
    
    // Get the port from environment or use default
    let port = env::var("PORT")
        .unwrap_or_else(|_| "3000".to_string())
        .parse::<u16>()?;
    
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    
    info!("Server listening on {}", addr);
    
    // Run the server
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    
    Ok(())
}

// For Lambda deployment
#[cfg(feature = "lambda")]
pub async fn lambda_handler() -> Result<(), Box<dyn std::error::Error>> {
    use lambda_web::{is_running_on_lambda, run};
    
    // Initialize tracing
    init_tracing();
    
    info!("Starting Passport Scorer Lambda function");
    
    // Create database connection pool
    let pool = create_connection_pool().await?;
    
    // Create the app
    let app = create_app(pool);
    
    if is_running_on_lambda() {
        // Run as Lambda
        run(app).await
    } else {
        // Run as regular server for local testing
        run_server().await
    }
}