use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Fuck OpenTelemetry SDK, sending raw OTLP to Jaeger...");

    // Generate random IDs
    let trace_id = format!("{:032x}", rand::random::<u128>());
    let span_id = format!("{:016x}", rand::random::<u64>());

    // Current time in nanoseconds since epoch
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)?
        .as_nanos() as u64;

    // Raw OTLP JSON payload
    let payload = json!({
        "resourceSpans": [{
            "resource": {
                "attributes": [{
                    "key": "service.name",
                    "value": {"stringValue": "raw-otlp-test"}
                }]
            },
            "scopeSpans": [{
                "scope": {
                    "name": "manual"
                },
                "spans": [{
                    "traceId": trace_id,
                    "spanId": span_id,
                    "name": "IT-FUCKING-WORKS",
                    "kind": 1,
                    "startTimeUnixNano": now.to_string(),
                    "endTimeUnixNano": (now + 100_000_000).to_string(), // +100ms
                    "attributes": [
                        {
                            "key": "test.message",
                            "value": {"stringValue": "This better show up in Jaeger"}
                        },
                        {
                            "key": "test.value",
                            "value": {"intValue": "42"}
                        }
                    ],
                    "status": {
                        "code": 1  // OK
                    }
                }]
            }]
        }]
    });

    println!("Sending to http://localhost:4318/v1/traces");

    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:4318/v1/traces")
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await?;

    println!("Response: {} {}", response.status(), response.text().await?);

    println!("\n✅ If you got a 200 OK, check Jaeger for service 'raw-otlp-test'");
    println!("   Span name: 'IT-FUCKING-WORKS'");

    Ok(())
}