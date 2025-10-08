#!/bin/bash

# RUN THIS ON YOUR LOCAL MACHINE, NOT IN THE CODESPACE

echo "Building and running the telemetry test locally..."

# Build the test binary
cargo build --bin test_grpc_otlp

# Run it with your local Jaeger
RUST_LOG=opentelemetry=debug,opentelemetry_otlp=debug \
./target/debug/test_grpc_otlp

echo ""
echo "Now check http://localhost:16686 for service 'grpc-test'"
echo ""
echo "If no traces appear, try the HTTP version:"
echo "cargo run --bin test_sync_telemetry"
echo ""
echo "Then look for service 'sync-test' in Jaeger"