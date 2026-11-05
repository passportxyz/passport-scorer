# Configuration

Database connections, OpenTelemetry setup, and infrastructure configuration patterns.

## Django Database Connections

Django uses multiple database connections:

- **default**: Main database from DATABASE_URL env var
- **data_model**: Separate DB for data model from DATA_MODEL_DATABASE_URL
- **read_replica_0**: Read replica from READ_REPLICA_0_URL
- **read_replica_analytics**: Analytics read replica from READ_REPLICA_ANALYTICS_URL

### Connection Pooling

No explicit connection pooling or CONN_MAX_AGE settings found in base.py, meaning Django uses default behavior (new connection per request). In Lambda, connections are closed after each request via `close_old_connections()`.

### Rust Implementation Note

For Rust: RDS Proxy handles connection pooling at infrastructure level, so low connection count (5) in app is appropriate. See `api/scorer/settings/base.py` and `api/v2/aws_lambdas/stamp_score_GET.py`.

## OpenTelemetry Configuration

### ADOT Lambda Layer Sidecar

The ADOT (AWS Distro for OpenTelemetry) Lambda layer runs as a sidecar and handles ALL telemetry processing, batching, flushing, and export. The application does not need to manually flush spans or sleep to wait for export.

**Application Requirements**:

The application just needs to:
1. Send spans to the ADOT collector via OTLP (localhost:4318 for HTTP, localhost:4317 for gRPC)
2. Use BatchSpanProcessor (not SimpleSpanProcessor)
3. Let ADOT handle the rest

**IMPORTANT**: DO NOT add manual flush logic, sleep delays, or shutdown handlers for OpenTelemetry. The ADOT layer manages all of that automatically.

### OTEL Endpoint Configuration

The OpenTelemetry collector endpoints are intentionally HARDCODED based on the environment (Lambda vs local), NOT configurable via environment variables like OTEL_EXPORTER_OTLP_ENDPOINT.

This is simpler and more reliable than making it configurable. The ADOT sidecar in Lambda always listens on 0.0.0.0:4318, so localhost works fine.

### JSON Logging vs Span Events

The fmt layer configuration depends on whether OpenTelemetry is enabled:

**When OTEL is ENABLED**: Do NOT use `.with_span_events()` in JSON output. OpenTelemetry handles all span instrumentation and sends it to ADOT/Jaeger. The JSON logs are just for regular application logging.

**When OTEL is DISABLED**: CAN use `.with_span_events(fmt::format::FmtSpan::CLOSE)` for basic tracing visibility in logs for local development.

**Best Practice**: Conditional pattern based on OTEL_EXPORTER_OTLP_ENDPOINT presence keeps JSON logs clean in production while providing visibility in development. See `rust-scorer/src/api/server.rs`.
