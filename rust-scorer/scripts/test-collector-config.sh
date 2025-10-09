#!/bin/bash
# Test script to validate collector.yaml syntax using otelcol-contrib

echo "Testing collector.yaml configuration..."

# Use Docker to run the OpenTelemetry Collector with our config
docker run --rm \
  -v $(pwd)/collector.yaml:/etc/collector.yaml \
  otel/opentelemetry-collector-contrib:0.117.0 \
  --config=/etc/collector.yaml \
  validate

if [ $? -eq 0 ]; then
  echo "✅ collector.yaml is valid!"
else
  echo "❌ collector.yaml has errors"
  exit 1
fi