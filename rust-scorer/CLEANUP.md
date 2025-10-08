# Telemetry Debug Cleanup

## Test Files Created During Debugging

These test binaries were created while debugging telemetry issues. Most can be removed now that telemetry works.

### Keep These:
- `src/bin/test_telemetry.rs` - Good working example with BatchSpanProcessor
- `src/bin/fuck_it_raw_otlp.rs` - Useful for debugging when SDK fails

### Remove These (debugging artifacts):
- `src/bin/batch_processor_test.rs` - Duplicate of test_telemetry
- `src/bin/minimal_otlp_test.rs` - Early debugging attempt
- `src/bin/real_instrumentation.rs` - Complex custom layer attempt
- `src/bin/test_grpc_otlp.rs` - gRPC test (we use HTTP)
- `src/bin/test_http_jaeger.rs` - Another duplicate test
- `src/bin/test_manual_export.rs` - Manual connection test
- `src/bin/test_otlp_connection.rs` - Connection debugging
- `src/bin/test_sync_telemetry.rs` - Sync version (we use async)
- `src/bin/instrumented_otlp.rs` - Another instrumentation test

### Also Remove:
- `test-spans-http.rs` - Test file in root
- `RUN_THIS_LOCALLY.sh` - Debug script
- `test-your-jaeger.sh` - Debug script

## Cleanup Commands

```bash
# Option 1: Move to archive (safe)
mkdir -p telemetry-debug-archive
mv src/bin/batch_processor_test.rs telemetry-debug-archive/
mv src/bin/minimal_otlp_test.rs telemetry-debug-archive/
mv src/bin/real_instrumentation.rs telemetry-debug-archive/
mv src/bin/test_grpc_otlp.rs telemetry-debug-archive/
mv src/bin/test_http_jaeger.rs telemetry-debug-archive/
mv src/bin/test_manual_export.rs telemetry-debug-archive/
mv src/bin/test_otlp_connection.rs telemetry-debug-archive/
mv src/bin/test_sync_telemetry.rs telemetry-debug-archive/
mv src/bin/instrumented_otlp.rs telemetry-debug-archive/
mv test-spans-http.rs telemetry-debug-archive/
mv RUN_THIS_LOCALLY.sh telemetry-debug-archive/
mv test-your-jaeger.sh telemetry-debug-archive/

# Option 2: Delete (permanent)
rm src/bin/batch_processor_test.rs
rm src/bin/minimal_otlp_test.rs
rm src/bin/real_instrumentation.rs
rm src/bin/test_grpc_otlp.rs
rm src/bin/test_http_jaeger.rs
rm src/bin/test_manual_export.rs
rm src/bin/test_otlp_connection.rs
rm src/bin/test_sync_telemetry.rs
rm src/bin/instrumented_otlp.rs
rm test-spans-http.rs
rm RUN_THIS_LOCALLY.sh
rm test-your-jaeger.sh
```

## What's Left After Cleanup

### Production Code:
- `src/api/server.rs` - Clean telemetry initialization
- `src/main.rs` - Clean Lambda/local detection

### Test Tools:
- `src/bin/test_telemetry.rs` - Working telemetry test
- `src/bin/fuck_it_raw_otlp.rs` - Raw OTLP debugging tool

### Documentation:
- `TELEMETRY_SETUP.md` - How to use telemetry
- `TELEMETRY_STATUS.md` - Current status and fixes
- `docker-compose.jaeger.yml` - Local Jaeger setup
- `collector.yaml` - ADOT collector config for Lambda