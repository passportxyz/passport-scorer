use passport_scorer::api::server;
use tracing::{info, info_span, Instrument};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Set up environment for local testing with Jaeger
    // Note: In Rust 1.72+, set_var is unsafe
    unsafe {
        std::env::set_var("OTEL_ENABLED", "true");
        std::env::set_var("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces");
        std::env::set_var("OTEL_SERVICE_NAME", "rust-scorer-test");
        std::env::set_var("RUST_LOG", "info");
    }

    println!("🔧 Initializing telemetry...");
    server::init_tracing();

    println!("✅ Telemetry initialized with BatchSpanProcessor!");

    // Use async instrumentation for proper span context
    test_spans().await;

    // CRITICAL for BatchSpanProcessor: Wait for batch timeout!
    println!("⏳ Waiting for BatchSpanProcessor to export (5 second batch interval)...");
    tokio::time::sleep(tokio::time::Duration::from_secs(6)).await;

    // Provider will flush on drop when program exits

    println!("🎉 Test complete! Check Jaeger UI at http://localhost:16686");
    println!("   Service: rust-scorer-test");
    Ok(())
}

#[tracing::instrument]
async fn test_spans() {
    info!("Starting test operation");

    // Simulate nested operations with proper async instrumentation
    database_operation().await;
    validation_operation().await;
    score_calculation().await;

    info!("Test operation completed");
}

#[tracing::instrument(fields(operation = "load_scorer", db_name = "postgres"))]
async fn database_operation() {
    info!("Loading scorer configuration");
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
    info!("Scorer loaded successfully");
}

#[tracing::instrument(fields(stamps_count = 5, valid_count = 3))]
async fn validation_operation() {
    info!("Validating credentials");
    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
    info!("Validation complete");
}

#[tracing::instrument(fields(address = "0x1234567890abcdef", scorer_id = 1))]
async fn score_calculation() {
    info!("Calculating score");

    // Simulate sub-operations
    let weight_span = info_span!("apply_weights");
    async {
        info!("Applying scorer weights");
        tokio::time::sleep(tokio::time::Duration::from_millis(25)).await;
    }.instrument(weight_span).await;

    let threshold_span = info_span!("check_threshold");
    async {
        info!("Checking threshold");
        tokio::time::sleep(tokio::time::Duration::from_millis(25)).await;
    }.instrument(threshold_span).await;

    tokio::time::sleep(tokio::time::Duration::from_millis(25)).await;
    info!("Score calculated: 15.5");
}