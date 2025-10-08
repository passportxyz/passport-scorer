use passport_scorer::api::server;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Check if running on Lambda or locally
    if std::env::var("AWS_LAMBDA_FUNCTION_NAME").is_ok() {
        // Debug: List contents of /var/task in Lambda
        println!("=== DEBUG: /var/task contents ===");
        if let Ok(entries) = std::fs::read_dir("/var/task") {
            for entry in entries {
                if let Ok(entry) = entry {
                    println!("  - {}", entry.path().display());
                }
            }
        } else {
            println!("  ERROR: Could not read /var/task directory");
        }
        println!("=== END DEBUG ===");

        // Also check if collector.yaml exists specifically
        if std::path::Path::new("/var/task/collector.yaml").exists() {
            println!("✅ /var/task/collector.yaml EXISTS");
            // Try to read and print first few lines
            if let Ok(contents) = std::fs::read_to_string("/var/task/collector.yaml") {
                println!("First 100 chars: {}", &contents[..contents.len().min(100)]);
            }
        } else {
            println!("❌ /var/task/collector.yaml NOT FOUND");
        }

        // Running on Lambda - use lambda_http runtime
        server::init_tracing();
        let app = server::create_app().await?;
        lambda_http::run(app)
            .await
            .map_err(|e| format!("Lambda runtime error: {}", e))?;
        Ok(())
    } else {
        // Running locally - use regular HTTP server
        server::run_server().await
    }
}
