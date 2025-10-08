use passport_scorer::api::server;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Check if running on Lambda or locally
    if std::env::var("AWS_LAMBDA_FUNCTION_NAME").is_ok() {
        // Running on Lambda - use lambda_http runtime
        eprintln!("🚀 Running in AWS Lambda mode");
        server::init_tracing();
        let app = server::create_app().await?;
        lambda_http::run(app)
            .await
            .map_err(|e| format!("Lambda runtime error: {}", e))?;
        Ok(())
    } else {
        // Running locally - use regular HTTP server
        eprintln!("🏠 Running in local server mode");
        server::run_server().await
    }
}
