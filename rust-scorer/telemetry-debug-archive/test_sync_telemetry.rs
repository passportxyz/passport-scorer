/// Synchronous test to avoid async runtime issues with SimpleSpanProcessor
use opentelemetry::{global, KeyValue, trace::{Tracer, Span, Status}};
use opentelemetry_sdk::{trace::{SdkTracerProvider, SimpleSpanProcessor}, Resource};
use opentelemetry_otlp::{SpanExporter, WithExportConfig};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🔧 Initializing OTLP exporter...");

    // Build the OTLP exporter for HTTP
    let exporter = SpanExporter::builder()
        .with_http()
        .with_endpoint("http://localhost:4318")
        .build()?;

    println!("✅ Exporter created");

    // Create resource
    let resource = Resource::builder()
        .with_attribute(KeyValue::new("service.name", "sync-test"))
        .build();

    // Create provider with simple processor (immediate export)
    let provider = SdkTracerProvider::builder()
        .with_resource(resource)
        .with_span_processor(SimpleSpanProcessor::new(exporter))
        .build();

    // Set as global provider
    global::set_tracer_provider(provider.clone());
    println!("✅ Provider set");

    // Get tracer
    let tracer = global::tracer("sync-test");

    println!("📊 Creating test spans...");

    // Create a root span
    let mut root_span = tracer.start("root-operation");
    root_span.set_attribute(KeyValue::new("operation.type", "test"));

    // Create a child span
    {
        let mut child_span = tracer.start("child-operation");
        child_span.set_attribute(KeyValue::new("child.value", 123));
        std::thread::sleep(std::time::Duration::from_millis(50));
        child_span.set_status(Status::Ok);
        child_span.end();
        println!("  Child span ended");
    }

    std::thread::sleep(std::time::Duration::from_millis(100));
    root_span.set_status(Status::Ok);
    root_span.end();
    println!("  Root span ended");

    // Give time for export
    println!("⏳ Waiting for export...");
    std::thread::sleep(std::time::Duration::from_secs(2));

    println!("✅ Test complete!");
    println!("Check Jaeger UI at http://localhost:16686");
    println!("Service name: sync-test");

    // Provider will be dropped here, triggering final export
    Ok(())
}