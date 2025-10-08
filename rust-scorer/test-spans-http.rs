use opentelemetry::{global, KeyValue, trace::{Tracer, Span, Status}};
use opentelemetry_sdk::{trace::{SdkTracerProvider, SimpleSpanProcessor}, Resource};
use opentelemetry_otlp::{SpanExporter, WithExportConfig};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Testing HTTP OTLP export to YOUR Jaeger...");

    // HTTP endpoint that YOUR curl worked on
    let exporter = SpanExporter::builder()
        .with_http()
        .with_endpoint("http://localhost:4318")
        .build()
        .expect("Failed to create HTTP exporter");

    let resource = Resource::builder()
        .with_attribute(KeyValue::new("service.name", "http-test"))
        .build();

    let provider = SdkTracerProvider::builder()
        .with_resource(resource)
        .with_span_processor(SimpleSpanProcessor::new(exporter))
        .build();

    global::set_tracer_provider(provider.clone());

    let tracer = global::tracer("http-test");

    println!("Creating spans...");
    let mut span = tracer.start("test-operation");
    span.set_attribute(KeyValue::new("test.id", "12345"));
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
    span.end();
    println!("Span ended and should export immediately");

    // Give SimpleSpanProcessor time to export
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    println!("\nNOW CHECK JAEGER: http://localhost:16686");
    println!("Look for service: 'http-test'");

    Ok(())
}