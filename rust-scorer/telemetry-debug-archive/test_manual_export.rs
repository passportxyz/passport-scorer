/// Test manual OTLP export with raw HTTP client
use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🔍 Testing manual OTLP export...");

    // Create a minimal OTLP trace payload
    let trace_data = json!({
        "resourceSpans": [{
            "resource": {
                "attributes": [{
                    "key": "service.name",
                    "value": {"stringValue": "manual-test"}
                }]
            },
            "scopeSpans": [{
                "scope": {
                    "name": "manual-test"
                },
                "spans": [{
                    "traceId": "5b8aa5a2d2c872e8321cf37308d69df2",
                    "spanId": "051581bf3cb55c13",
                    "name": "test-span",
                    "kind": 1,
                    "startTimeUnixNano": "1644160357000000000",
                    "endTimeUnixNano": "1644160357100000000",
                    "attributes": [{
                        "key": "test.attribute",
                        "value": {"stringValue": "test-value"}
                    }]
                }]
            }]
        }]
    });

    // Try both IPv6 and IPv4
    let urls = vec![
        "http://[::1]:4318/v1/traces",       // IPv6
        "http://127.0.0.1:4318/v1/traces",   // IPv4
        "http://localhost:4318/v1/traces",   // Hostname
    ];

    let client = reqwest::Client::new();

    for url in urls {
        println!("📤 Trying: {}", url);
        match client
            .post(url)
            .header("Content-Type", "application/json")
            .json(&trace_data)
            .send()
            .await
        {
            Ok(response) => {
                println!("  ✅ Connected!");
                let status = response.status();
                println!("  📨 Response status: {}", status);
                let body = response.text().await?;
                println!("  📨 Response body: {}", body);

                if status.is_success() {
                    println!("✅ Success! Traces were accepted");
                    println!("🔍 Check Jaeger UI for service 'manual-test'");
                    return Ok(());
                }
            }
            Err(e) => {
                println!("  ❌ Failed: {}", e);
                continue;
            }
        }
    }

    println!("❌ Could not connect to Jaeger on any address");
    Ok(())
}