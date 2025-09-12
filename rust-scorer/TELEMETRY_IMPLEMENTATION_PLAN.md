# Rust Scorer Telemetry Implementation Plan

## Executive Summary

Replace the current broken flamegraph/tracing-flame setup with proper OpenTelemetry distributed tracing. This will provide actual timing data for production performance analysis.

## Current Problems

1. **Wrong Tool**: Flamegraphs show CPU sampling, not I/O wait times (useless for DB-heavy service)
2. **No Timing Data**: Current spans show hierarchy but no millisecond measurements
3. **Unreadable Output**: Raw JSON logs with tokio internals, no proper visualization
4. **Manual Analysis**: Building custom tools instead of using industry-standard solutions

## Proposed Solution

Implement OpenTelemetry with automatic instrumentation, exporting to Jaeger (dev) and AWS X-Ray (production).

## Implementation Steps

### Phase 1: Remove Broken Infrastructure

**Remove dependencies:**
- `tracing-flame`
- `inferno` 
- Custom log analyzer tool

**Remove code:**
- Flamegraph generation logic
- Manual span creation with inline guards
- Custom timing measurements

### Phase 2: Add OpenTelemetry

**Dependencies to add:**
```toml
[dependencies]
opentelemetry = "0.24"
opentelemetry_sdk = "0.24"
opentelemetry-otlp = "0.24"
tracing-opentelemetry = "0.26"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json", "fmt"] }
# Note: sqlx already includes tracing integration by default in modern versions
```

**Main.rs setup:**
```rust
use opentelemetry::trace::TracerProvider;
use opentelemetry_sdk::{trace::Sampler, Resource};
use opentelemetry_otlp::WithExportConfig;
use tracing_subscriber::prelude::*;

fn init_telemetry() {
    let endpoint = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT")
        .unwrap_or_else(|_| "http://localhost:4317".to_string());
    
    let sample_rate = std::env::var("OTEL_SAMPLING_RATIO")
        .unwrap_or_else(|_| "1.0".to_string())
        .parse()
        .unwrap_or(1.0);

    let resource = Resource::new(vec![
        opentelemetry::KeyValue::new("service.name", "rust-scorer"),
        opentelemetry::KeyValue::new("service.version", env!("CARGO_PKG_VERSION")),
        opentelemetry::KeyValue::new("deployment.environment", 
            std::env::var("ENVIRONMENT").unwrap_or_else(|_| "development".to_string())),
    ]);

    let tracer = opentelemetry_otlp::new_pipeline()
        .tracing()
        .with_exporter(
            opentelemetry_otlp::new_exporter()
                .tonic()
                .with_endpoint(endpoint)
        )
        .with_trace_config(
            opentelemetry_sdk::trace::config()
                .with_sampler(Sampler::TraceIdRatioBased(sample_rate))
                .with_resource(resource)
        )
        .install_batch(opentelemetry_sdk::runtime::Tokio)
        .expect("Failed to initialize OpenTelemetry");

    // ONE tracing system, TWO outputs:
    // - fmt layer → JSON logs to stdout/CloudWatch  
    // - opentelemetry layer → Traces to Jaeger/X-Ray
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::fmt::layer()
                .json()  // JSON format for CloudWatch
                .with_target(false)  // Clean logs without module paths
                .with_span_events(tracing_subscriber::fmt::format::FmtSpan::CLOSE)
        )
        .with(tracing_opentelemetry::layer().with_tracer(tracer))
        .with(tracing_subscriber::EnvFilter::from_default_env())
        .init();
}
```

### Phase 3: Audit and Clean Up Logs

**Audit existing logs to remove redundancy:**
- Remove manual DB query logging (SQLx handles this automatically)
- Remove "entering function" debug logs (spans handle this)
- Remove timing logs (OpenTelemetry measures this)
- Keep only business-relevant events (user actions, errors, decisions)

**SQLx creates BOTH logs and telemetry spans:**
- **Log output**: `INFO sqlx::query: query took 23ms rows_returned=5`
- **Telemetry span**: Full timing data with query details in Jaeger/X-Ray
- Don't manually log "Executing query" or "Query returned N rows" - SQLx does this

**Good logs to keep:**
```rust
// Business events
tracing::info!(user_id = %id, score = %score, "Score calculated");
tracing::warn!(retry_count = 3, "LIFO dedup retry limit reached");
tracing::error!(error = ?e, "API key validation failed");

// NOT needed (redundant):
tracing::debug!("Loading community from database");  // SQLx logs this
tracing::info!("Query took {}ms", elapsed);  // OpenTelemetry tracks this
```

### Phase 4: Instrument Functions

**Add to async functions (but not every function):**
```rust
#[tracing::instrument(skip(pool, large_params), fields(user_id = %user_id))]
async fn score_address_handler(
    address: String,
    pool: PgPool,
) -> Result<Score> {
    // Function automatically creates child span with timing
}
```

**Key functions to instrument:**
- `score_address_handler` - Main entry point
- `validate_api_key` - Often slow on cold starts
- `validate_credentials_batch` - CPU intensive
- `lifo_dedup` - Complex logic with multiple DB ops
- `calculate_score` - Business logic
- `process_human_points` - Multiple DB operations

**DON'T instrument these (SQLx already does):**
- `load_community` - Simple DB query
- `load_ceramic_cache` - Simple DB query
- Other single-query database functions

### Phase 5: Development Setup

**Local Jaeger:**
```bash
# docker-compose.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

**Run locally:**
```bash
docker-compose up -d
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 cargo run
# View traces at http://localhost:16686
```

### Phase 6: Production Configuration

**Environment variables:**
```bash
# Development
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SAMPLING_RATIO=1.0  # 100% sampling in dev

# Staging  
OTEL_EXPORTER_OTLP_ENDPOINT=https://xray.us-east-1.amazonaws.com
OTEL_SAMPLING_RATIO=0.1  # 10% sampling
ENVIRONMENT=staging

# Production
OTEL_EXPORTER_OTLP_ENDPOINT=https://xray.us-east-1.amazonaws.com
OTEL_SAMPLING_RATIO=0.01  # 1% sampling initially
ENVIRONMENT=production
```

**Lambda configuration:**
- Add X-Ray permissions to Lambda IAM role
- Set environment variables in Pulumi config
- Enable X-Ray tracing on Lambda function

## Cost Analysis

### Development (Free)
- Local Jaeger: $0

### Staging 
- AWS X-Ray free tier: 100k traces/month free
- Above free tier: ~$5/month with 10% sampling

### Production
- 10 req/sec = 26M requests/month
- With 1% sampling = 260k traces
- Cost: ~$1.50/month
- Can increase sampling during incidents

### Alternative: Self-hosted Jaeger on ECS
- Break-even point: ~10M traces/month
- Not worth it until much higher volume

## Success Metrics

1. **Cold start latency** - Identify exact bottleneck (likely DB connection)
2. **P95 latency breakdown** - See which operations are slow
3. **Database query performance** - Identify N+1 queries or missing indexes
4. **Error correlation** - Link errors to specific slow operations

## Rollout Plan

1. **Week 1**: Implement in development, test with local Jaeger
2. **Week 2**: Deploy to staging with X-Ray, 10% sampling
3. **Week 3**: Production deploy with 1% sampling
4. **Week 4**: Analyze data, increase sampling if needed

## What You Get

Instead of unreadable JSON logs, you'll see:

```
score_address_handler (total: 198ms)
├── validate_api_key (45ms)
│   └── verify_pbkdf2_hash (43ms)
├── load_community (23ms)
│   └── SQL: SELECT * FROM community (22ms)
├── load_ceramic_cache (87ms)
│   └── SQL: SELECT * FROM ceramic_cache (85ms)
├── validate_credentials (31ms)
│   ├── parse_credentials (2ms)
│   └── verify_signatures (29ms)
└── calculate_score (12ms)
```

With automatic P50/P95/P99 percentiles, error rates, and bottleneck detection.

## How Tracing Works (Single System, Multiple Outputs)

**Key Concept**: The `tracing` crate is ONE instrumentation system that sends data to MULTIPLE outputs:

1. **You instrument once**: Use `#[instrument]` for spans, `tracing::info!()` for events
2. **Subscriber routes to multiple outputs**:
   - `fmt::layer()` → Sends logs to stdout/CloudWatch
   - `opentelemetry::layer()` → Sends traces to Jaeger/X-Ray
   - Both layers receive ALL tracing data

**Example**:
```rust
#[tracing::instrument]  // Creates a SPAN (timing data)
async fn process_request(id: u64) {
    tracing::info!("Processing request");  // Creates an EVENT (log message)
    // BOTH the span and event go through tracing
    // fmt layer logs: "INFO Processing request"
    // otel layer sends: span with timing to Jaeger
}
```

## SQLx Query Tracing

SQLx automatically creates tracing spans for queries (included by default, not a feature flag).

**Log levels**:
- `sqlx=info`: Query timing and row counts (no SQL text)
- `sqlx=debug`: Full SQL queries + timing
- `sqlx=warn`: Only errors

**Example output at INFO**:
```
INFO sqlx::query: query took 23ms rows_returned=5
```

**Recommended settings**:
```bash
# Production
RUST_LOG=info,sqlx=info,hyper=warn,tower=warn,h2=error

# Development  
RUST_LOG=debug,sqlx=debug

# Debugging specific module
RUST_LOG=info,rust_scorer::dedup=trace,sqlx=info
```

## Log Levels Best Practices

- **error!** - Actionable problems requiring immediate attention (payment failed, DB down)
- **warn!** - Concerning but handled issues to review daily (retry succeeded, fallback used)
- **info!** - Business events and metrics (user scored, API called, request completed)
- **debug!** - Development info (entering function, intermediate values)
- **trace!** - Verbose debugging (rarely used in production code)

## Notes for Implementation Team

1. **Don't overthink it** - Just add `#[instrument]` to functions and let OpenTelemetry handle the rest
2. **Start with high-level functions** - You can add more granular instrumentation later
3. **Use skip() for large params** - Prevents huge logs: `#[instrument(skip(pool, credentials))]`
4. **Add relevant fields** - Include user/request context: `fields(user_id = %id)`
5. **Don't log sensitive data** - No passwords, API keys, or PII in spans

## Common Pitfalls to Avoid

1. **Don't create manual spans** - Let `#[instrument]` do it
2. **Don't log everything** - Use sampling in production
3. **Don't forget skip()** - Large params will bloat your traces
4. **Don't use sync code in async** - It won't show proper timing
5. **Don't ignore cold starts** - They're often the biggest latency source