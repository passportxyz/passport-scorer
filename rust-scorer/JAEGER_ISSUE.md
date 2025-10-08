# Jaeger Connection Issue

## Problem
The OpenTelemetry spans are being created correctly in the Rust code, but they're not being exported to Jaeger.

## Root Cause
**Jaeger is not running or not accessible on port 4318.**

When you ran:
```bash
curl -v http://localhost:4318/v1/traces
```
It worked and returned `405 Method Not Allowed` (which is correct for GET).

But when our Rust code tries to connect, it gets `Connection refused`, and now curl also fails.

## Solution

1. **Ensure Jaeger is running**:
```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  -e COLLECTOR_OTLP_ENABLED=true \
  jaegertracing/all-in-one:latest
```

2. **Verify it's running**:
```bash
docker ps | grep jaeger
curl -X POST http://localhost:4318/v1/traces -H "Content-Type: application/json" -d '{}'
```

3. **Then run the telemetry test**:
```bash
cargo run --bin test_sync_telemetry
```

## The Code is Correct

The telemetry configuration is working:
- ✅ Spans are being created (visible in JSON logs)
- ✅ OpenTelemetry is initialized with correct endpoint
- ✅ SimpleSpanProcessor is being used for immediate export
- ✅ Tracing instrumentation is on all key functions

The only issue is that Jaeger needs to be running to receive the spans.