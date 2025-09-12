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
use tracing_flame::{FlameLayer, FlushGuard};
use once_cell::sync::OnceCell;

// Global storage for the flame guard to keep it alive
static FLAME_GUARD: OnceCell<FlushGuard<std::io::BufWriter<std::fs::File>>> = OnceCell::new();

use crate::api::handler::score_address_handler;

pub fn init_tracing() {
    // Normal JSON logging always enabled
    let registry = tracing_subscriber::registry()
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
        );
    
    // Add flame layer if FLAME environment variable is set
    if env::var("FLAME").is_ok() {
        eprintln!("🔥 Flame tracing enabled - writing to ./tracing.folded");
        let (flame_layer, guard) = FlameLayer::with_file("./tracing.folded")
            .expect("Could not create flame layer");
        
        // Store the guard globally to keep it alive and ensure flushing
        FLAME_GUARD.set(guard).ok();
        
        registry.with(flame_layer).init();
    } else {
        registry.init();
    }
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

pub async fn create_app() -> Result<Router, Box<dyn std::error::Error>> {
    // Create database connection pool
    let pool = create_connection_pool().await?;
    
    Ok(Router::new()
        // Main v2 scoring endpoint
        .route(
            "/v2/stamps/{scorer_id}/score/{address}",
            get(score_address_handler),
        )
        // Health check endpoint
        .route("/health", get(health_check))
        // Add connection pool as state
        .with_state(pool)
        // Add tracing layer for observability
        .layer(TraceLayer::new_for_http()))
}

async fn health_check() -> &'static str {
    "OK"
}

pub async fn run_server() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    init_tracing();
    
    info!("Starting Passport Scorer Rust server");
    
    // Set up ctrl-c handler to flush flame data
    let shutdown = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install CTRL+C signal handler");
        eprintln!("Shutting down gracefully...");
        
        // Flame data will auto-flush when guard is dropped at program exit
        if FLAME_GUARD.get().is_some() {
            eprintln!("Flame data will be flushed to tracing.folded");
        }
    };
    
    // Create the app
    let app = create_app().await?;
    
    // Get the port from environment or use default
    let port = env::var("PORT")
        .unwrap_or_else(|_| "3000".to_string())
        .parse::<u16>()?;
    
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    
    info!("Server listening on {}", addr);
    
    // Run the server with graceful shutdown
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await?;
    
    Ok(())
}

