use axum::{
    routing::get,
    Router,
};
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use std::env;
use std::net::SocketAddr;
use std::time::Duration;
use tower_http::trace::TraceLayer;
use tracing::info;
use tracing_subscriber::{fmt, EnvFilter, prelude::*};
use opentelemetry::KeyValue;
use opentelemetry::trace::TracerProvider as _;  // Import as _ since we only need the trait methods
use opentelemetry_sdk::{trace::SdkTracerProvider, Resource};
use opentelemetry_otlp::{SpanExporter, WithExportConfig};
use tracing_opentelemetry::OpenTelemetryLayer;

use crate::api::handler::score_address_handler;

pub fn init_tracing() {
    // Check if we're in Lambda environment
    let is_lambda = env::var("AWS_LAMBDA_FUNCTION_NAME").is_ok();

    // Get OpenTelemetry configuration from environment
    let enable_otel = env::var("OTEL_ENABLED")
        .unwrap_or_else(|_| if is_lambda { "true" } else { "false" }.to_string()) == "true";

    // OTLP endpoint - try 127.0.0.1 in case localhost doesn't resolve in Lambda
    let otel_endpoint = if is_lambda {
        "http://127.0.0.1:4318/v1/traces".to_string()
    } else {
        "http://localhost:4318/v1/traces".to_string()
    };

    // Base subscriber - only add fmt layer if NOT using OTEL (they conflict)
    let subscriber = tracing_subscriber::registry()
        .with(
            if !enable_otel {
                // Only add fmt layer when NOT using OpenTelemetry
                Some(fmt::layer()
                    .json() // JSON format for CloudWatch
                    .with_target(false)
                    .with_span_events(fmt::format::FmtSpan::CLOSE)) // Log span close with duration
            } else {
                // When using OTEL, still need basic logging but without span events
                Some(fmt::layer()
                    .json()
                    .with_target(false))
            }
        )
        .with(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info,sqlx=info,hyper=warn,tower=warn,h2=error"))
        );

    // Add OpenTelemetry layer if enabled
    if enable_otel {
        println!("🔵 OTEL: Attempting to initialize with endpoint: {}", otel_endpoint);
        match init_opentelemetry(&otel_endpoint) {
            Ok(provider) => {
                println!("✅ OTEL: Provider created successfully");

                // Set as global provider for other uses
                opentelemetry::global::set_tracer_provider(provider.clone());

                // Get tracer directly from provider for OpenTelemetryLayer
                // (global::tracer returns BoxedTracer which doesn't implement PreSampledTracer)
                let tracer = provider.tracer("rust-scorer");
                println!("✅ OTEL: Tracer created, attaching to subscriber");

                // Test if we can create a span directly
                use opentelemetry::trace::Tracer;
                let test_span = tracer.start("INIT-TEST-SPAN");
                drop(test_span);
                println!("🔵 OTEL: Created test span during init");

                subscriber
                    .with(OpenTelemetryLayer::new(tracer))
                    .init();

                println!("✅ OTEL: OpenTelemetry layer initialized and attached");
            }
            Err(e) => {
                println!("❌ OTEL ERROR: Failed to initialize OpenTelemetry: {}", e);
                tracing::error!("Failed to initialize OpenTelemetry: {}. Continuing with logs only.", e);
                subscriber.init();
            }
        }
    } else {
        println!("⚠️ OTEL: Disabled (OTEL_ENABLED != true)");
        subscriber.init();
    }
}

fn init_opentelemetry(endpoint: &str) -> Result<SdkTracerProvider, Box<dyn std::error::Error>> {
    let environment = env::var("ENVIRONMENT")
        .unwrap_or_else(|_| "development".to_string());

    // Service name can be overridden by environment variable
    let service_name = env::var("OTEL_SERVICE_NAME")
        .unwrap_or_else(|_| "rust-scorer".to_string());

    let resource = Resource::builder()
        .with_attribute(KeyValue::new("service.name", service_name))
        .with_attribute(KeyValue::new("service.version", env!("CARGO_PKG_VERSION")))
        .with_attribute(KeyValue::new("deployment.environment", environment))
        .build();

    // Check if endpoint is HTTP or gRPC based
    let exporter = if endpoint.starts_with("http://") || endpoint.starts_with("https://") {
        println!("🔵 OTEL: Creating HTTP exporter for endpoint: {}", endpoint);
        // HTTP endpoint (AWS ADOT collector uses HTTP on port 4318)
        let exporter = SpanExporter::builder()
            .with_http()
            .with_endpoint(endpoint)
            .build()?;
        println!("✅ OTEL: HTTP exporter created successfully");
        exporter
    } else {
        println!("🔵 OTEL: Creating gRPC exporter for endpoint: {}", endpoint);
        // gRPC endpoint
        let exporter = SpanExporter::builder()
            .with_tonic()
            .with_endpoint(endpoint)
            .build()?;
        println!("✅ OTEL: gRPC exporter created successfully");
        exporter
    };

    // Wrap exporter with debugging to see if it's being called
    use opentelemetry_sdk::trace::{SpanData, SpanExporter as SpanExporterTrait};
    use std::fmt::Debug;

    #[derive(Debug)]
    struct DebugExporter<E> {
        inner: E,
    }

    impl<E: SpanExporterTrait> SpanExporterTrait for DebugExporter<E> {
        async fn export(&self, spans: Vec<SpanData>) -> opentelemetry_sdk::error::OTelSdkResult {
            println!("🔴 OTEL EXPORT: Attempting to export {} spans", spans.len());
            for span in &spans {
                println!("  - Span: {} ({:?})", span.name, span.span_kind);
            }
            let result = self.inner.export(spans).await;
            match &result {
                Ok(_) => println!("🔴 OTEL EXPORT: Success"),
                Err(e) => println!("🔴 OTEL EXPORT: Error = {:?}", e),
            }
            result
        }

        fn shutdown(&mut self) -> opentelemetry_sdk::error::OTelSdkResult {
            println!("🔴 OTEL EXPORT: Shutdown called");
            self.inner.shutdown()
        }

        fn force_flush(&mut self) -> opentelemetry_sdk::error::OTelSdkResult {
            println!("🔴 OTEL EXPORT: Force flush called");
            self.inner.force_flush()
        }
    }

    let debug_exporter = DebugExporter { inner: exporter };

    println!("🔵 OTEL: Building TracerProvider with BatchSpanProcessor (wrapped with debug)");

    // In Lambda, use a much shorter batch interval to ensure timely exports
    let provider = if env::var("AWS_LAMBDA_FUNCTION_NAME").is_ok() {
        use opentelemetry_sdk::trace::{BatchConfig, BatchSpanProcessor};
        use std::time::Duration;

        let batch_config = BatchConfig::default()
            .with_scheduled_delay(Duration::from_secs(1)); // 1 second in Lambda vs default 5 seconds

        println!("🔵 OTEL: Using 1-second batch interval for Lambda environment");

        let processor = BatchSpanProcessor::new(debug_exporter, batch_config);

        SdkTracerProvider::builder()
            .with_resource(resource)
            .with_span_processor(processor)
            .build()
    } else {
        // Use default batch config (5 seconds) for non-Lambda
        SdkTracerProvider::builder()
            .with_resource(resource)
            .with_batch_exporter(debug_exporter)
            .build()
    };

    println!("✅ OTEL: TracerProvider built successfully");
    Ok(provider)
}

pub async fn create_connection_pool() -> Result<PgPool, Box<dyn std::error::Error>> {
    let mut database_url = env::var("DATABASE_URL")
        .or_else(|_| env::var("RDS_PROXY_URL"))
        .expect("DATABASE_URL or RDS_PROXY_URL must be set (either directly or via SCORER_SERVER_SSM_ARN)");

    // Ensure SSL mode is set for RDS Proxy/RDS connections
    // If the URL doesn't already have sslmode parameter, add it
    if !database_url.contains("sslmode=") {
        let separator = if database_url.contains('?') { "&" } else { "?" };
        database_url = format!("{}{}sslmode=require", database_url, separator);
        info!("Added sslmode=require to database URL");
    }

    info!("Creating database connection pool");

    // Keep connection count low - RDS Proxy handles actual pooling
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .min_connections(1)
        .acquire_timeout(Duration::from_secs(3))
        .connect(&database_url)
        .await?;

    info!("Database connection pool created successfully");

    Ok(pool)
}

pub async fn create_app() -> Result<Router, Box<dyn std::error::Error>> {
    // Load secrets from AWS Secrets Manager if SCORER_SERVER_SSM_ARN is set
    // This happens at startup (Lambda cold start or local/ECS server initialization)
    // Mimics Python Lambda behavior in api/aws_lambdas/utils.py:36-58
    crate::secrets::load_secrets_from_manager().await?;

    // Create database connection pool
    let pool = create_connection_pool().await?;
    
    Ok(Router::new()
        // Main v2 scoring endpoint
        .route(
            "/v2/stamps/{scorer_id}/score/{address}",
            get(score_address_handler),
        )
        // Health check endpoint
        .route("/health", get(health_check))
        // Add connection pool as state
        .with_state(pool)
        // Add tracing layer for observability
        .layer(TraceLayer::new_for_http()))
}

async fn health_check() -> &'static str {
    "OK"
}

pub async fn run_server() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    init_tracing();

    info!("Starting Passport Scorer Rust server");

    // Set up ctrl-c handler for graceful shutdown
    let shutdown = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install CTRL+C signal handler");
        eprintln!("Shutting down gracefully...");
    };
    
    // Create the app
    let app = create_app().await?;
    
    // Get the port from environment or use default
    let port = env::var("PORT")
        .unwrap_or_else(|_| "3000".to_string())
        .parse::<u16>()?;
    
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    
    info!("Server listening on {}", addr);
    
    // Run the server with graceful shutdown
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await?;
    
    Ok(())
}

