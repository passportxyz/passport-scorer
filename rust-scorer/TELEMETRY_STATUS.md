# OpenTelemetry Telemetry Status & Issues

## Current Status (2025-10-08)

### ✅ What Works
1. **Jaeger is running** and accepting OTLP data on port 4318
2. **Raw OTLP export works** - We can manually send JSON spans to Jaeger (`fuck_it_raw_otlp.rs`)
3. **Tracing instrumentation** - Our `#[tracing::instrument]` annotations are creating spans
4. **BatchSpanProcessor** doesn't panic (unlike SimpleSpanProcessor in async)

### ❌ Current Issues

#### 1. Wrong OTLP Endpoint URL
**Error**: `BatchSpanProcessor.ExportError: Operation failed: 404, url: "http://localhost:4318/"`

**Problem**: The OTLP exporter is hitting the base URL instead of the traces endpoint
- Wrong: `http://localhost:4318/`
- Correct: `http://localhost:4318/v1/traces`

**Root Cause**: The `SpanExporter::builder().with_http().with_endpoint()` might not be appending the `/v1/traces` path automatically

#### 2. SimpleSpanProcessor Panics
**Error**: `Cannot drop a runtime in a context where blocking is not allowed`

**Problem**: SimpleSpanProcessor uses blocking I/O which panics in async contexts
**Solution**: Must use BatchSpanProcessor in async applications

## File Structure

### Working Examples
- `src/bin/fuck_it_raw_otlp.rs` - ✅ Bypasses SDK, sends raw JSON to Jaeger
- Shows nested spans working when sent directly

### Broken Examples
- `src/bin/test_telemetry.rs` - ❌ Uses server init, hits wrong endpoint
- `src/bin/batch_processor_test.rs` - ❌ Same endpoint issue
- `src/api/server.rs` - ❌ Telemetry init with wrong endpoint

## Fix Needed

The OpenTelemetry OTLP exporter needs the full endpoint URL:

```rust
// Current (broken)
let exporter = SpanExporter::builder()
    .with_http()
    .with_endpoint("http://localhost:4318")  // Missing /v1/traces
    .build()?;

// Should be
let exporter = SpanExporter::builder()
    .with_http()
    .with_endpoint("http://localhost:4318/v1/traces")  // Full endpoint
    .build()?;
```

## Architecture Notes

### Correct Flow
1. Application with `#[tracing::instrument]` →
2. `OpenTelemetryLayer` collects spans →
3. `BatchSpanProcessor` batches spans (5 sec interval) →
4. `SpanExporter` sends to OTLP endpoint →
5. Jaeger receives at `http://localhost:4318/v1/traces`

### Current Issues in Flow
- Step 4 is hitting wrong URL (`/` instead of `/v1/traces`)

## Testing Checklist

- [x] Jaeger running (`docker ps | grep jaeger`)
- [x] Port 4318 accessible (`curl -X POST http://localhost:4318/v1/traces`)
- [x] Raw OTLP works (`cargo run --bin fuck_it_raw_otlp`)
- [ ] SDK export works (blocked by endpoint issue)
- [ ] Traces appear in Jaeger UI

## Fix Applied

✅ **Fixed in commit d420324**
- Updated all endpoints to use full URL: `http://localhost:4318/v1/traces`
- Files updated:
  - `src/api/server.rs`
  - `src/bin/test_telemetry.rs`
  - `src/bin/batch_processor_test.rs`

## How to Test

```bash
# Run the test with correct endpoint
cargo run --bin test_telemetry

# Or run the batch processor test
cargo run --bin batch_processor_test

# Check Jaeger UI
open http://localhost:16686
# Look for service: "rust-scorer-test" or "batch-processor-test"
```

## Environment Variables

Working configuration:
```bash
export OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces  # Need full path!
export OTEL_SERVICE_NAME=rust-scorer
```

## Lambda Considerations

For Lambda deployment:
- Must use BatchSpanProcessor (SimpleSpanProcessor will panic)
- ADOT layer runs collector at localhost:4318
- Need `OPENTELEMETRY_COLLECTOR_CONFIG_URI=/var/task/collector.yaml`
- collector.yaml must be in Lambda package