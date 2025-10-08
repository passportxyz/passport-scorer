use reqwest;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🔍 Testing OTLP endpoint connectivity...");

    // Test if we can reach the OTLP HTTP endpoint
    let endpoint = "http://localhost:4318/v1/traces";

    println!("📡 Attempting to connect to: {}", endpoint);

    match reqwest::Client::new()
        .post(endpoint)
        .header("Content-Type", "application/x-protobuf")
        .body(vec![]) // Empty body just to test connection
        .send()
        .await
    {
        Ok(response) => {
            println!("✅ Connection successful!");
            println!("   Status: {}", response.status());
            if response.status() == 404 {
                println!("   Note: 404 is expected for empty request - endpoint exists");
            }
        },
        Err(e) => {
            println!("❌ Connection failed: {}", e);
            if e.is_connect() {
                println!("   Is Jaeger running? Try:");
                println!("   docker run -d --name jaeger -p 4318:4318 -e COLLECTOR_OTLP_ENABLED=true jaegertracing/all-in-one:latest");
            }
        }
    }

    Ok(())
}