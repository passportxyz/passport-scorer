use opentelemetry::{global, KeyValue, trace::{Tracer, Span}};
use opentelemetry_sdk::{trace::{SdkTracerProvider, SimpleSpanProcessor}, Resource};
use opentelemetry_otlp::{SpanExporter, WithExportConfig};

fn init_tracer() -> Result<(), Box<dyn std::error::Error>> {
    println!("🔧 Initializing minimal OTLP tracer...");

    // Build the OTLP exporter for HTTP
    let exporter = SpanExporter::builder()
        .with_http()
        .with_endpoint("http://localhost:4318")
        .build()?;

    println!("✅ Exporter created");

    // Create resource
    let resource = Resource::builder()
        .with_attribute(KeyValue::new("service.name", "minimal-test"))
        .build();

    // Create provider with simple processor (immediate export)
    let provider = SdkTracerProvider::builder()
        .with_resource(resource)
        .with_span_processor(SimpleSpanProcessor::new(exporter))
        .build();

    // Set as global provider
    global::set_tracer_provider(provider.clone());

    println!("✅ Tracer provider set globally");
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    init_tracer()?;

    let tracer = global::tracer("minimal-test");

    println!("📊 Creating test span...");
    let mut span = tracer.start("test-span");
    span.set_attribute(KeyValue::new("test.value", 42));
    println!("  Span created, sleeping...");
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
    span.end();
    println!("  Span ended");

    // Force flush
    println!("⏳ Waiting for export...");
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    println!("✅ Done! Check Jaeger at http://localhost:16686");
    Ok(())
}