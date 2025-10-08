# AWS OpenTelemetry Configuration for Rust Scorer Lambda

## Overview

The Rust Scorer Lambda is configured to send telemetry data (traces, metrics, logs) to AWS X-Ray using the AWS Distro for OpenTelemetry (ADOT) Lambda layer.

## Architecture

```
Rust Application → OTLP → ADOT Collector (localhost:4318) → AWS X-Ray
```

## Configuration Files

### 1. collector.yaml
This file configures the ADOT collector that runs as part of the Lambda layer. It:
- Receives OTLP data on localhost:4318 (HTTP) and localhost:4317 (gRPC)
- Exports traces to AWS X-Ray
- Includes memory limiting and batching for optimal Lambda performance

### 2. Environment Variables (set in Pulumi)
- `OTEL_ENABLED`: "true" - Enables OpenTelemetry
- `OTEL_EXPORTER_OTLP_ENDPOINT`: "http://localhost:4318" - ADOT collector endpoint
- `OPENTELEMETRY_COLLECTOR_CONFIG_URI`: "/var/task/collector.yaml" - Path to collector config
- `OTEL_SERVICE_NAME`: "rust-scorer" - Service name in traces
- `AWS_LAMBDA_EXEC_WRAPPER`: "/opt/otel-instrument" - Enables auto-instrumentation

## Build Process

The `build-lambda-zip.sh` script:
1. Builds the Rust binary using cargo-lambda
2. Packages the collector.yaml file into the deployment zip
3. Creates a Lambda-ready artifact at `target/lambda/rust-scorer/bootstrap.zip`

## Testing Telemetry

### Local Testing with Jaeger

1. Start Jaeger using Docker Compose:
```bash
docker-compose -f docker-compose.jaeger.yml up -d
```

2. Run the test script (which sets up environment and runs the app):
```bash
./test-telemetry.sh
```

Or run manually:
```bash
export OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=rust-scorer-local
cargo run
```

3. View traces in Jaeger UI:
   - Open http://localhost:16686
   - Select "rust-scorer-local" service
   - Click "Find Traces"

4. Test the telemetry binary:
```bash
cargo run --bin test_telemetry
```
This creates sample spans to verify the instrumentation is working.

### Lambda Testing

After deployment:

1. Check CloudWatch Logs for the Lambda function:
   - Look for JSON formatted logs with trace information
   - Check for any OTEL initialization errors

2. Check AWS X-Ray:
   - Navigate to AWS X-Ray console
   - Look for traces from service "rust-scorer"
   - Verify trace segments show database queries and API calls

3. Test with header-based routing:
```bash
curl -H "X-Use-Rust-Scorer: true" \
     https://api.passport.xyz/v2/stamps/{scorer_id}/score/{address}
```

## Troubleshooting

### No traces appearing in X-Ray

1. Check Lambda has ADOT layer attached (ARM64 version)
2. Verify IAM role has X-Ray write permissions
3. Check CloudWatch logs for OTEL errors
4. Ensure collector.yaml is in the Lambda package

### Traces incomplete or missing segments

1. Verify SimpleSpanProcessor is used (not BatchSpanProcessor)
2. Check spans are properly ended before Lambda freezes
3. Review memory limits - collector needs ~50MB overhead

### Connection errors to collector

1. Ensure endpoint is http://localhost:4318 (not external URL)
2. Verify ADOT layer is compatible with Lambda runtime (ARM64)
3. Check collector.yaml syntax is valid

## Key Differences from Python Implementation

- Uses SimpleSpanProcessor for immediate export (Lambda compatibility)
- HTTP endpoint (4318) preferred over gRPC for ADOT layer
- JSON structured logging integrated with tracing spans
- Automatic service name and environment detection