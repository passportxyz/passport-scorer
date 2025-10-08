#!/bin/bash
set -e

echo "🔍 Testing OpenTelemetry with Jaeger..."

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not available. Please install Docker to run this test."
    exit 1
fi

# Start Jaeger
echo "🚀 Starting Jaeger..."
docker run -d --name jaeger \
    -p 16686:16686 \
    -p 4317:4317 \
    -p 4318:4318 \
    -p 14268:14268 \
    -p 14250:14250 \
    -e COLLECTOR_OTLP_ENABLED=true \
    jaegertracing/all-in-one:latest \
    2>/dev/null || echo "Jaeger already running"

# Wait for Jaeger to be ready
echo "⏳ Waiting for Jaeger to be ready..."
sleep 5

# Export environment variables for local testing
export OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=rust-scorer-local
export RUST_LOG=info,sqlx=info,hyper=warn,tower=warn

# Check if database is configured
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set. Using test database."
    export DATABASE_URL="postgresql://postgres:postgres@localhost/passport_scorer_test"
fi

echo "📊 Configuration:"
echo "  - Jaeger UI: http://localhost:16686"
echo "  - OTLP Endpoint: $OTEL_EXPORTER_OTLP_ENDPOINT"
echo "  - Service Name: $OTEL_SERVICE_NAME"

echo ""
echo "🏃 Starting Rust scorer with telemetry enabled..."
echo "Send requests to http://localhost:3000/v2/stamps/{scorer_id}/score/{address}"
echo ""
echo "📈 View traces at: http://localhost:16686"
echo ""

# Run the application
cargo run

# Cleanup on exit
echo ""
echo "🧹 Cleaning up..."
docker stop jaeger >/dev/null 2>&1
docker rm jaeger >/dev/null 2>&1