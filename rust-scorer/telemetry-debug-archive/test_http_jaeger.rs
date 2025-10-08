use opentelemetry::{global, KeyValue, trace::{Tracer, Span, Status}};
use opentelemetry_sdk::{trace::{SdkTracerProvider, SimpleSpanProcessor}, Resource};
use opentelemetry_otlp::{SpanExporter, WithExportConfig};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    unsafe {
        std::env::set_var("RUST_LOG", "opentelemetry=debug,opentelemetry_otlp=debug");
    }
    env_logger::init();

    println!("🚀 Testing HTTP OTLP export to YOUR LOCAL Jaeger...");
    println!("   Using http://localhost:4318 (the endpoint YOUR curl worked on)");

    // HTTP endpoint - port 4318
    let exporter = SpanExporter::builder()
        .with_http()
        .with_endpoint("http://localhost:4318")
        .build()
        .expect("Failed to create HTTP exporter");

    println!("✅ HTTP Exporter created");

    let resource = Resource::builder()
        .with_attribute(KeyValue::new("service.name", "FUCKING-FINALLY"))
        .build();

    let provider = SdkTracerProvider::builder()
        .with_resource(resource)
        .with_span_processor(SimpleSpanProcessor::new(exporter))
        .build();

    global::set_tracer_provider(provider.clone());
    println!("✅ Provider set");

    let tracer = global::tracer("test");

    println!("📊 Creating spans RIGHT NOW...");

    let mut root = tracer.start("THIS-BETTER-WORK");
    root.set_attribute(KeyValue::new("test.value", 69420));

    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

    root.set_status(Status::Ok);
    root.end();

    println!("⚡ Span ended - SimpleSpanProcessor exports IMMEDIATELY");

    // Wait for export
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    println!("\n🎯 GO CHECK JAEGER RIGHT NOW:");
    println!("   1. Open http://localhost:16686");
    println!("   2. Select service: 'FUCKING-FINALLY'");
    println!("   3. Click 'Find Traces'");
    println!("   4. You should see a trace called 'THIS-BETTER-WORK'");
    println!("\nIf no traces appear, your Jaeger isn't configured for OTLP.");

    Ok(())
}