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
use opentelemetry::KeyValue;
use opentelemetry::trace::TracerProvider;
use opentelemetry_sdk::{trace::SdkTracerProvider, Resource};
use opentelemetry_otlp::SpanExporter;
use tracing_opentelemetry::OpenTelemetryLayer;

use crate::api::handler::score_address_handler;

pub fn init_tracing() {
    // Get OpenTelemetry configuration from environment
    let otel_endpoint = env::var("OTEL_EXPORTER_OTLP_ENDPOINT")
        .unwrap_or_else(|_| "http://localhost:4317".to_string());
    
    let enable_otel = env::var("OTEL_ENABLED")
        .unwrap_or_else(|_| "true".to_string()) == "true";
    
    
    // Base subscriber with JSON logging for CloudWatch
    let subscriber = tracing_subscriber::registry()
        .with(
            fmt::layer()
                .json() // JSON format for CloudWatch
                .with_target(false)
                .with_span_events(fmt::format::FmtSpan::CLOSE) // Log span close with duration
        )
        .with(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info,sqlx=info,hyper=warn,tower=warn,h2=error"))
        );
    
    // Add OpenTelemetry layer if enabled
    if enable_otel {
        match init_opentelemetry(&otel_endpoint) {
            Ok(provider) => {
                info!("OpenTelemetry initialized with endpoint: {}", otel_endpoint);
                let tracer = provider.tracer("rust-scorer");
                subscriber
                    .with(OpenTelemetryLayer::new(tracer))
                    .init();
            }
            Err(e) => {
                eprintln!("Failed to initialize OpenTelemetry: {}. Continuing with logs only.", e);
                subscriber.init();
            }
        }
    } else {
        info!("OpenTelemetry disabled, using JSON logging only");
        subscriber.init();
    }
}

fn init_opentelemetry(endpoint: &str) -> Result<SdkTracerProvider, Box<dyn std::error::Error>> {
    let environment = env::var("ENVIRONMENT")
        .unwrap_or_else(|_| "development".to_string());

    let resource = Resource::builder()
        .with_attribute(KeyValue::new("service.name", "rust-scorer"))
        .with_attribute(KeyValue::new("service.version", env!("CARGO_PKG_VERSION")))
        .with_attribute(KeyValue::new("deployment.environment", environment))
        .build();

    // Set endpoint via environment variable (unsafe in Rust 1.66+)
    unsafe {
        env::set_var("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint);
    }
    
    let exporter = SpanExporter::builder()
        .with_tonic()
        .build()?;
    
    let provider = SdkTracerProvider::builder()
        .with_resource(resource)
        .with_batch_exporter(exporter)
        .build();

    Ok(provider)
}

pub async fn create_connection_pool() -> Result<PgPool, Box<dyn std::error::Error>> {
    let database_url = env::var("DATABASE_URL")
        .or_else(|_| env::var("RDS_PROXY_URL"))
        .expect("DATABASE_URL or RDS_PROXY_URL must be set (either directly or via SCORER_SERVER_SSM_ARN)");
    
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
    // Load secrets from AWS Secrets Manager if SCORER_SERVER_SSM_ARN is set
    // This happens at startup (Lambda cold start or local/ECS server initialization)
    // Mimics Python Lambda behavior in api/aws_lambdas/utils.py:36-58
    crate::secrets::load_secrets_from_manager().await?;

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

    // Set up ctrl-c handler for graceful shutdown
    let shutdown = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install CTRL+C signal handler");
        eprintln!("Shutting down gracefully...");
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

