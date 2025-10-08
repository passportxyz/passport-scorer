# ADOT Collector Configuration Fixes

## Issue
The OpenTelemetry collector extension was failing to initialize in Lambda with error:
```
"Failed to start the extension","error":"unable to start, otelcol state is Closed"
```

## Root Causes and Fixes

### 1. Invalid `loglevel` field in logging exporter
**Problem**: The logging exporter had a `loglevel: info` field which is not valid.
**Fix**: Removed the loglevel field entirely.

### 2. Outdated exporter name for ADOT v0.117.0
**Problem**: ADOT versions 0.86.0+ use `debug` instead of `logging` for the debug exporter.
**Fix**: Changed all references from `logging` to `debug` in exporters and pipelines.

### 3. Missing telemetry section
**Problem**: Some ADOT versions require a telemetry section for the collector itself.
**Fix**: Added telemetry section with log level and metrics configuration.

## Final Working Configuration

The collector.yaml now includes:
- OTLP receivers on ports 4317 (gRPC) and 4318 (HTTP)
- AWS X-Ray exporter for traces
- Debug exporter for troubleshooting
- Memory limiter and batch processors
- Telemetry configuration for the collector itself

## Testing

To validate the collector configuration locally (requires Docker):
```bash
./test-collector-config.sh
```

## Deployment

The collector.yaml is packaged into the Lambda deployment:
- For ZIP deployment: `build-lambda-zip.sh` includes it
- Must be at `/var/task/collector.yaml` in Lambda environment
- Set environment variable: `OPENTELEMETRY_COLLECTOR_CONFIG_URI=/var/task/collector.yaml`