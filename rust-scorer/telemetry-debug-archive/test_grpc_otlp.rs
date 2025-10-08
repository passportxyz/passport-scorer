/// Test OTLP export using gRPC endpoint
use opentelemetry::{global, KeyValue, trace::{Tracer, Span, Status}};
use opentelemetry_sdk::{trace::{SdkTracerProvider, SimpleSpanProcessor, TraceError}, Resource};
use opentelemetry_otlp::{SpanExporter, WithExportConfig};

fn init_tracer() -> Result<SdkTracerProvider, Box<dyn std::error::Error>> {
    println!("🔧 Initializing OTLP exporter for gRPC...");

    // Build the OTLP exporter for gRPC (port 4317)
    let exporter = SpanExporter::builder()
        .with_tonic()
        .with_endpoint("http://localhost:4317")  // gRPC endpoint
        .build()
        .map_err(|e| format!("Failed to build exporter: {}", e))?;

    println!("✅ Exporter created for gRPC endpoint");

    // Create resource
    let resource = Resource::builder()
        .with_attribute(KeyValue::new("service.name", "grpc-test"))
        .with_attribute(KeyValue::new("service.version", "1.0.0"))
        .build();

    // Create provider with simple processor (immediate export)
    let provider = SdkTracerProvider::builder()
        .with_resource(resource)
        .with_span_processor(SimpleSpanProcessor::new(exporter))
        .build();

    Ok(provider)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Set debug logging
    unsafe {
        std::env::set_var("RUST_LOG", "opentelemetry=debug,opentelemetry_otlp=debug");
    }
    env_logger::init();

    let provider = init_tracer()?;

    // Set as global provider
    global::set_tracer_provider(provider.clone());
    println!("✅ Provider set globally");

    // Get tracer
    let tracer = global::tracer("grpc-test");

    println!("📊 Creating test spans...");

    // Create a root span with context
    let mut root = tracer.start("grpc-root-operation");
    root.set_attribute(KeyValue::new("test.type", "grpc"));
    root.set_attribute(KeyValue::new("test.value", 42));

    println!("  Root span created");
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

    // Create child span
    {
        let mut child = tracer.start("grpc-child-operation");
        child.set_attribute(KeyValue::new("child.id", "child-1"));
        tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
        child.set_status(Status::Ok);
        child.end();
        println!("  Child span ended");
    }

    root.set_status(Status::Ok);
    root.end();
    println!("  Root span ended");

    // Force flush by dropping and recreating
    println!("⏳ Forcing flush...");
    drop(provider);
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    println!("✅ Test complete!");
    println!("Check Jaeger UI at http://localhost:16686");
    println!("Service name: grpc-test");

    Ok(())
}