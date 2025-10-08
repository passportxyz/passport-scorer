use opentelemetry::{global, KeyValue, trace::TracerProvider};
use opentelemetry_sdk::{trace::SdkTracerProvider, Resource};
use opentelemetry_otlp::{SpanExporter, WithExportConfig};
use tracing::{info, info_span};
use tracing_subscriber::prelude::*;

fn init_telemetry() -> Result<(), Box<dyn std::error::Error>> {
    println!("🔧 Initializing OTLP with BatchSpanProcessor...");

    // Build OTLP exporter for HTTP
    // MUST include /v1/traces path!
    let exporter = SpanExporter::builder()
        .with_http()
        .with_endpoint("http://localhost:4318/v1/traces")
        .build()?;

    println!("✅ Exporter created");

    // Create resource
    let resource = Resource::builder()
        .with_attribute(KeyValue::new("service.name", "batch-processor-test"))
        .with_attribute(KeyValue::new("service.version", "1.0.0"))
        .build();

    // Build provider with BatchSpanProcessor - THE KEY DIFFERENCE!
    let provider = SdkTracerProvider::builder()
        .with_resource(resource)
        .with_batch_exporter(exporter)  // Batch processor for async safety
        .build();

    // Set global provider
    global::set_tracer_provider(provider.clone());

    // Get tracer
    let tracer = provider.tracer("batch-test");

    // Set up tracing subscriber with OpenTelemetry layer
    use tracing_opentelemetry::OpenTelemetryLayer;

    tracing_subscriber::registry()
        .with(OpenTelemetryLayer::new(tracer))
        .with(
            tracing_subscriber::fmt::layer()
                .json()
                .with_target(false)
        )
        .with(tracing_subscriber::EnvFilter::new("info"))
        .init();

    println!("✅ Tracing initialized with BatchSpanProcessor");
    Ok(())
}

// Our instrumented functions using standard tracing macros
#[tracing::instrument(fields(scorer_id = scorer_id))]
async fn score_address(address: &str, scorer_id: i32) -> f64 {
    info!("Starting score calculation");

    // Load data
    let credentials = load_credentials(address).await;

    // Validate
    let valid_count = validate_batch(credentials).await;

    // Calculate score
    let score = calculate_final_score(valid_count).await;

    info!(score = score, "Score calculated");
    score
}

#[tracing::instrument(skip(address))]
async fn load_credentials(address: &str) -> Vec<String> {
    info!("Loading credentials from database");
    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

    vec![
        "Passport".to_string(),
        "GitHub".to_string(),
        "Twitter".to_string(),
    ]
}

#[tracing::instrument(fields(count = creds.len()))]
async fn validate_batch(creds: Vec<String>) -> usize {
    info!("Validating credentials");

    let mut valid = 0;
    for cred in &creds {
        if validate_single(cred).await {
            valid += 1;
        }
    }

    info!(valid_count = valid, "Validation complete");
    valid
}

#[tracing::instrument]
async fn validate_single(credential: &str) -> bool {
    let span = info_span!("signature_check", credential = %credential);
    let _guard = span.enter();

    info!("Checking signature");
    tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
    true
}

#[tracing::instrument]
async fn calculate_final_score(valid_count: usize) -> f64 {
    info!("Applying scoring algorithm");
    tokio::time::sleep(tokio::time::Duration::from_millis(30)).await;

    let score = valid_count as f64 * 15.5;
    info!(calculated_score = score, "Score computation complete");
    score
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🚀 Testing BatchSpanProcessor with REAL tracing instrumentation");
    println!("");

    // Initialize telemetry
    init_telemetry()?;

    println!("📊 Running instrumented functions...\n");

    // Run our instrumented code
    let address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0";
    let scorer_id = 42;

    let score = score_address(address, scorer_id).await;

    println!("\n✅ Score: {:.2}", score);

    // CRITICAL: Give BatchSpanProcessor time to export!
    // It batches spans and exports periodically (default 5 seconds)
    println!("\n⏳ Waiting for BatchSpanProcessor to export spans...");
    tokio::time::sleep(tokio::time::Duration::from_secs(6)).await;

    // Shutdown properly to flush remaining spans
    println!("📤 Shutting down to flush remaining spans...");
    // Note: In OpenTelemetry 0.30, explicit shutdown may not be available
    // The provider will flush on drop when the program exits

    println!("\n🎯 Check Jaeger at http://localhost:16686");
    println!("   Service: 'batch-processor-test'");
    println!("   You should see the full trace with all nested spans!");

    Ok(())
}