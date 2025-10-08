use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{info, Instrument};
use tracing_subscriber::prelude::*;
use serde_json::json;

// Store spans in memory to send later
#[derive(Debug, Clone)]
struct SpanData {
    trace_id: String,
    span_id: String,
    parent_id: Option<String>,
    name: String,
    start_time: u64,
    end_time: Option<u64>,
    attributes: Vec<(String, String)>,
}

#[derive(Clone)]
struct OtlpCollector {
    spans: Arc<Mutex<Vec<SpanData>>>,
}

impl OtlpCollector {
    fn new() -> Self {
        Self {
            spans: Arc::new(Mutex::new(Vec::new())),
        }
    }

    async fn flush_to_jaeger(&self) -> Result<(), Box<dyn std::error::Error>> {
        let spans = {
            let mut spans = self.spans.lock().unwrap();
            std::mem::take(&mut *spans)
        };

        if spans.is_empty() {
            return Ok(());
        }

        // Convert our spans to OTLP format
        let otlp_spans: Vec<_> = spans.iter().map(|span| {
            json!({
                "traceId": &span.trace_id,
                "spanId": &span.span_id,
                "parentSpanId": span.parent_id.as_ref(),
                "name": &span.name,
                "kind": 1,
                "startTimeUnixNano": span.start_time.to_string(),
                "endTimeUnixNano": span.end_time.unwrap_or(span.start_time + 1000000).to_string(),
                "attributes": span.attributes.iter().map(|(k, v)| {
                    json!({
                        "key": k,
                        "value": {"stringValue": v}
                    })
                }).collect::<Vec<_>>(),
                "status": {"code": 1}
            })
        }).collect();

        let payload = json!({
            "resourceSpans": [{
                "resource": {
                    "attributes": [{
                        "key": "service.name",
                        "value": {"stringValue": "real-instrumentation"}
                    }]
                },
                "scopeSpans": [{
                    "scope": {"name": "tracing"},
                    "spans": otlp_spans
                }]
            }]
        });

        println!("📤 Sending {} spans to Jaeger", spans.len());
        let client = reqwest::Client::new();
        let response = client
            .post("http://localhost:4318/v1/traces")
            .header("Content-Type", "application/json")
            .json(&payload)
            .send()
            .await?;

        println!("✅ Response: {}", response.status());
        Ok(())
    }
}

// Simple subscriber that collects span data
impl<S> tracing_subscriber::Layer<S> for OtlpCollector
where
    S: tracing::Subscriber + for<'lookup> tracing_subscriber::registry::LookupSpan<'lookup>,
{
    fn on_new_span(
        &self,
        attrs: &tracing::span::Attributes<'_>,
        id: &tracing::span::Id,
        ctx: tracing_subscriber::layer::Context<'_, S>,
    ) {
        let metadata = attrs.metadata();
        let name = metadata.name();

        // Generate IDs
        let span_id = format!("{:016x}", rand::random::<u64>());
        let trace_id = format!("{:032x}", rand::random::<u128>());

        let span_data = SpanData {
            trace_id,
            span_id: span_id.clone(),
            parent_id: None, // Would need to track parent context
            name: name.to_string(),
            start_time: SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos() as u64,
            end_time: None,
            attributes: vec![],
        };

        // Store the span
        if let Some(span) = ctx.span(id) {
            span.extensions_mut().insert(span_data.clone());
        }
        self.spans.lock().unwrap().push(span_data);
    }

    fn on_close(&self, id: tracing::span::Id, ctx: tracing_subscriber::layer::Context<'_, S>) {
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos() as u64;

        if let Some(span) = ctx.span(&id) {
            if let Some(data) = span.extensions().get::<SpanData>() {
                // Update end time in our collected spans
                let mut spans = self.spans.lock().unwrap();
                for span in spans.iter_mut() {
                    if span.span_id == data.span_id {
                        span.end_time = Some(now);
                        break;
                    }
                }
            }
        }
    }
}

// Now the actual instrumented functions!

#[tracing::instrument]
async fn score_address(address: &str, scorer_id: i32) -> String {
    info!("Starting score calculation");

    // Call nested functions
    let cache = load_cache(address).await;
    let validated = validate_credentials(&cache).await;
    let score = calculate_score(validated).await;

    info!("Score calculated: {}", score);
    format!("Score for {}: {}", address, score)
}

#[tracing::instrument(skip(address))]
async fn load_cache(address: &str) -> Vec<String> {
    info!("Loading from ceramic cache");
    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
    vec!["cred1".to_string(), "cred2".to_string(), "cred3".to_string()]
}

#[tracing::instrument(skip(credentials))]
async fn validate_credentials(credentials: &[String]) -> usize {
    info!("Validating {} credentials", credentials.len());

    // Nested span for each credential
    for (i, cred) in credentials.iter().enumerate() {
        validate_single_credential(cred, i).await;
    }

    credentials.len()
}

#[tracing::instrument]
async fn validate_single_credential(cred: &str, index: usize) {
    info!("Validating credential {}: {}", index, cred);
    tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
}

#[tracing::instrument]
async fn calculate_score(valid_count: usize) -> f64 {
    info!("Calculating score from {} valid stamps", valid_count);
    tokio::time::sleep(tokio::time::Duration::from_millis(30)).await;
    valid_count as f64 * 5.0
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🚀 Testing REAL instrumentation with raw OTLP export");

    // Create our collector
    let collector = OtlpCollector::new();
    let collector_clone = collector.clone();

    // Set up tracing with our custom layer
    tracing_subscriber::registry()
        .with(collector.clone())
        .with(tracing_subscriber::fmt::layer())
        .init();

    println!("📊 Running instrumented functions...");

    // Call our instrumented function
    let result = score_address("0xdeadbeef", 42).await;
    println!("Result: {}", result);

    // Flush spans to Jaeger
    println!("\n🔄 Flushing spans to Jaeger...");
    collector_clone.flush_to_jaeger().await?;

    println!("\n✅ Check Jaeger for service 'real-instrumentation'");
    println!("   You should see the nested trace structure!");

    Ok(())
}