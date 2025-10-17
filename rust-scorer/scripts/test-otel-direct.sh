#!/bin/bash

# Test direct OTEL span creation (bypassing tracing layer)

cat > src/bin/test_otel_direct.rs << 'EOF'
use opentelemetry::trace::{Tracer, TracerProvider};
use opentelemetry::KeyValue;
use opentelemetry_otlp::SpanExporter;
use opentelemetry_sdk::{trace::SdkTracerProvider, Resource};
use std::time::Duration;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🔵 Testing direct OTEL span creation (no tracing layer)");

    let endpoint = "http://127.0.0.1:4318/v1/traces";
    println!("🔵 Using endpoint: {}", endpoint);

    // Create exporter
    let exporter = SpanExporter::builder()
        .with_http()
        .with_endpoint(endpoint)
        .build()?;
    println!("✅ Exporter created");

    // Create provider with short batch interval
    use opentelemetry_sdk::trace::{BatchConfig, BatchSpanProcessor};

    let batch_config = BatchConfig::default()
        .with_scheduled_delay(Duration::from_millis(500)); // 500ms batch interval

    let processor = BatchSpanProcessor::new(exporter, batch_config);

    let provider = SdkTracerProvider::builder()
        .with_resource(Resource::builder()
            .with_attribute(KeyValue::new("service.name", "otel-direct-test"))
            .build())
        .with_span_processor(processor)
        .build();

    println!("✅ Provider created with 500ms batch interval");

    // Get tracer
    let tracer = provider.tracer("test-tracer");

    // Create spans directly
    println!("🔵 Creating test spans...");

    for i in 0..3 {
        let mut span = tracer.start(format!("test-span-{}", i));
        span.set_attribute(KeyValue::new("test.index", i as i64));
        println!("  Created span: test-span-{}", i);
        span.end();
    }

    println!("🔵 Waiting for batch export (1 second)...");
    tokio::time::sleep(Duration::from_secs(1)).await;

    // Force flush before shutdown
    println!("🔵 Force flushing spans...");
    let _ = provider.force_flush();

    println!("🔵 Shutting down provider...");
    let _ = provider.shutdown();

    println!("✅ Test complete - check if collector received spans");

    Ok(())
}
EOF

echo "Running test..."
OTEL_ENABLED=true cargo run --bin test_otel_direct