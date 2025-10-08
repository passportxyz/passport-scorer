use serde_json::json;
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{info, info_span, Instrument};
use tracing_subscriber::prelude::*;

// Our actual business logic with instrumentation
#[tracing::instrument(fields(scorer_id = scorer_id))]
async fn score_address(address: &str, scorer_id: i32) -> Result<f64, Box<dyn std::error::Error>> {
    info!("Processing score request");

    // Simulate loading from database
    let credentials = load_ceramic_cache(address).await?;

    // Validate the credentials
    let valid_stamps = validate_credentials(credentials).await?;

    // Calculate the final score
    let score = calculate_weighted_score(&valid_stamps).await?;

    info!(score = score, "Score calculated successfully");
    Ok(score)
}

#[tracing::instrument(skip(address), fields(db = "ceramic_cache"))]
async fn load_ceramic_cache(address: &str) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    info!("Querying database for credentials");
    tokio::time::sleep(tokio::time::Duration::from_millis(75)).await;

    // Simulate loaded credentials
    Ok(vec![
        "GitcoinPassport".to_string(),
        "GitHub".to_string(),
        "Discord".to_string(),
        "Twitter".to_string(),
        "LinkedIn".to_string(),
    ])
}

#[tracing::instrument(fields(count = credentials.len()))]
async fn validate_credentials(credentials: Vec<String>) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    info!("Validating {} credentials", credentials.len());

    let mut valid = Vec::new();

    for credential in credentials {
        let span = info_span!("validate_single", credential = %credential);
        let is_valid = async {
            info!("Checking signature");
            tokio::time::sleep(tokio::time::Duration::from_millis(20)).await;
            // Simulate 80% valid
            rand::random::<f32>() > 0.2
        }.instrument(span).await;

        if is_valid {
            valid.push(credential);
        }
    }

    info!(valid_count = valid.len(), "Validation complete");
    Ok(valid)
}

#[tracing::instrument(fields(stamp_count = stamps.len()))]
async fn calculate_weighted_score(stamps: &[String]) -> Result<f64, Box<dyn std::error::Error>> {
    info!("Calculating weighted score");

    let weights = vec![10.0, 5.0, 3.0, 2.0, 1.0];
    let mut score = 0.0;

    for (i, stamp) in stamps.iter().enumerate() {
        let weight = weights.get(i).unwrap_or(&1.0);
        score += weight;
        info!(stamp = %stamp, weight = weight, "Adding stamp weight");
    }

    tokio::time::sleep(tokio::time::Duration::from_millis(30)).await;
    Ok(score)
}

// Function to manually build and send OTLP data from our trace
async fn send_trace_to_jaeger(
    trace_id: String,
    root_name: &str,
    duration_ms: u64,
) -> Result<(), Box<dyn std::error::Error>> {
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos() as u64;

    // Build a simplified trace representation
    // In reality, you'd collect this from the tracing subscriber
    let payload = json!({
        "resourceSpans": [{
            "resource": {
                "attributes": [{
                    "key": "service.name",
                    "value": {"stringValue": "instrumented-scorer"}
                }]
            },
            "scopeSpans": [{
                "scope": {"name": "tracing"},
                "spans": [{
                    "traceId": trace_id,
                    "spanId": format!("{:016x}", rand::random::<u64>()),
                    "name": root_name,
                    "kind": 1,
                    "startTimeUnixNano": now.to_string(),
                    "endTimeUnixNano": (now + duration_ms * 1_000_000).to_string(),
                    "attributes": [
                        {
                            "key": "operation.type",
                            "value": {"stringValue": "score_calculation"}
                        }
                    ],
                    "status": {"code": 1}
                }]
            }]
        }]
    });

    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:4318/v1/traces")
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await?;

    println!("📤 Sent trace to Jaeger: {}", response.status());
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🚀 Testing REAL instrumented functions");
    println!("   Using #[tracing::instrument] with manual OTLP export");

    // Initialize tracing (just console output for now)
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer())
        .with(tracing_subscriber::EnvFilter::new("info"))
        .init();

    // Generate a trace ID for this execution
    let trace_id = format!("{:032x}", rand::random::<u128>());

    println!("\n📊 Running instrumented scoring function...\n");

    let start = std::time::Instant::now();

    // Call our real instrumented function
    let address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0";
    let scorer_id = 42;

    match score_address(address, scorer_id).await {
        Ok(score) => {
            println!("\n✅ Score calculated: {:.2}", score);
        }
        Err(e) => {
            println!("\n❌ Error: {}", e);
        }
    }

    let duration = start.elapsed();
    println!("⏱️  Total time: {:?}", duration);

    // Send a simplified version to Jaeger
    // (In production, you'd have a proper tracing layer that collects all spans)
    println!("\n📤 Sending trace to Jaeger...");
    send_trace_to_jaeger(
        trace_id,
        "score_address",
        duration.as_millis() as u64,
    ).await?;

    println!("\n🎯 Check Jaeger for service 'instrumented-scorer'");
    println!("   Note: This is simplified - a real implementation would");
    println!("   capture ALL the spans from the instrumentation!");

    Ok(())
}