use passport_scorer::api::server;
use tracing::{info, info_span};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Set up environment for local testing with Jaeger
    // Note: In Rust 1.72+, set_var is unsafe
    unsafe {
        std::env::set_var("OTEL_ENABLED", "true");
        std::env::set_var("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318");
        std::env::set_var("OTEL_SERVICE_NAME", "rust-scorer-test");
        std::env::set_var("RUST_LOG", "info");
    }

    println!("🔧 Initializing telemetry...");
    server::init_tracing();

    println!("✅ Telemetry initialized!");

    // Create some test spans
    let span = info_span!("test_main_operation");
    let _guard = span.enter();

    info!("Starting test operation");

    // Simulate some nested operations
    {
        let span = info_span!("database_operation", operation = "load_scorer");
        let _guard = span.enter();
        info!("Loading scorer configuration");
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
    }

    {
        let span = info_span!("validation", stamps_count = 5);
        let _guard = span.enter();
        info!("Validating credentials");
        tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
    }

    {
        let span = info_span!("score_calculation", address = "0x123...");
        let _guard = span.enter();
        info!("Calculating score");
        tokio::time::sleep(tokio::time::Duration::from_millis(75)).await;
    }

    info!("Test operation completed");

    // Give time for spans to be exported
    println!("⏳ Waiting for spans to export...");
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    println!("🎉 Test complete! Check Jaeger UI at http://localhost:16686");
    Ok(())
}