
use passport_scorer::api::server;

#[cfg(not(feature = "lambda"))]
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    server::run_server().await
}

#[cfg(feature = "lambda")]
#[tokio::main]
async fn main() -> Result<(), lambda_runtime::Error> {
    // Initialize tracing with OpenTelemetry support
    server::init_tracing();

    // Create the Axum app
    let app = server::create_app().await
        .map_err(|e| lambda_runtime::Error::from(e.to_string()))?;
    
    // Run with lambda_web adapter
    lambda_web::run(app).await
}
