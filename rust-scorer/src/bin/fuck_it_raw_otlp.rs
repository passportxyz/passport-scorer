use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Fuck OpenTelemetry SDK, sending raw OTLP to Jaeger...");

    // Generate IDs - same trace ID for all spans
    let trace_id = format!("{:032x}", rand::random::<u128>());
    let root_span_id = format!("{:016x}", rand::random::<u64>());
    let child1_span_id = format!("{:016x}", rand::random::<u64>());
    let child2_span_id = format!("{:016x}", rand::random::<u64>());
    let grandchild_span_id = format!("{:016x}", rand::random::<u64>());

    // Current time in nanoseconds since epoch
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)?
        .as_nanos() as u64;

    // Raw OTLP JSON payload with NESTED SPANS
    let payload = json!({
        "resourceSpans": [{
            "resource": {
                "attributes": [{
                    "key": "service.name",
                    "value": {"stringValue": "raw-otlp-nested"}
                }]
            },
            "scopeSpans": [{
                "scope": {
                    "name": "manual"
                },
                "spans": [
                    // ROOT SPAN
                    {
                        "traceId": trace_id,
                        "spanId": root_span_id,
                        "name": "ROOT-OPERATION",
                        "kind": 1,  // SPAN_KIND_INTERNAL
                        "startTimeUnixNano": now.to_string(),
                        "endTimeUnixNano": (now + 500_000_000).to_string(), // +500ms total
                        "attributes": [
                            {
                                "key": "operation.type",
                                "value": {"stringValue": "score_request"}
                            },
                            {
                                "key": "address",
                                "value": {"stringValue": "0x1234567890abcdef"}
                            }
                        ],
                        "status": {"code": 1}  // OK
                    },
                    // CHILD 1: Database Query
                    {
                        "traceId": trace_id,
                        "spanId": child1_span_id,
                        "parentSpanId": root_span_id,  // PARENT REFERENCE!
                        "name": "database.query",
                        "kind": 3,  // SPAN_KIND_CLIENT
                        "startTimeUnixNano": (now + 50_000_000).to_string(), // starts 50ms after root
                        "endTimeUnixNano": (now + 150_000_000).to_string(),  // 100ms duration
                        "attributes": [
                            {
                                "key": "db.system",
                                "value": {"stringValue": "postgresql"}
                            },
                            {
                                "key": "db.statement",
                                "value": {"stringValue": "SELECT * FROM ceramic_cache WHERE address = $1"}
                            }
                        ],
                        "status": {"code": 1}
                    },
                    // CHILD 2: Validation
                    {
                        "traceId": trace_id,
                        "spanId": child2_span_id,
                        "parentSpanId": root_span_id,  // PARENT REFERENCE!
                        "name": "validate.credentials",
                        "kind": 1,
                        "startTimeUnixNano": (now + 200_000_000).to_string(), // starts 200ms after root
                        "endTimeUnixNano": (now + 400_000_000).to_string(),   // 200ms duration
                        "attributes": [
                            {
                                "key": "credentials.count",
                                "value": {"intValue": "5"}
                            },
                            {
                                "key": "credentials.valid",
                                "value": {"intValue": "3"}
                            }
                        ],
                        "status": {"code": 1}
                    },
                    // GRANDCHILD: Nested under validation
                    {
                        "traceId": trace_id,
                        "spanId": grandchild_span_id,
                        "parentSpanId": child2_span_id,  // PARENT IS CHILD2!
                        "name": "validate.signature",
                        "kind": 1,
                        "startTimeUnixNano": (now + 250_000_000).to_string(), // during validation
                        "endTimeUnixNano": (now + 300_000_000).to_string(),   // 50ms duration
                        "attributes": [
                            {
                                "key": "signature.algorithm",
                                "value": {"stringValue": "EdDSA"}
                            }
                        ],
                        "status": {"code": 1}
                    }
                ]
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

    println!("\n✅ If you got a 200 OK, check Jaeger for service 'raw-otlp-nested'");
    println!("   You should see a trace with:");
    println!("   📊 ROOT-OPERATION (500ms)");
    println!("      ├── database.query (100ms)");
    println!("      └── validate.credentials (200ms)");
    println!("           └── validate.signature (50ms)");

    Ok(())
}