#!/bin/bash
set -e

# Build Rust Lambda as zip artifact for ARM64
# This script builds the rust-scorer Lambda function using cargo-lambda
# and produces a ready-to-deploy zip file

echo "Building Rust Lambda for ARM64..."

# Ensure cargo-lambda is installed
if ! command -v cargo-lambda &> /dev/null; then
    echo "Installing cargo-lambda..."
    cargo install cargo-lambda
fi

# Build for ARM64 Lambda with offline mode (for sqlx)
export SQLX_OFFLINE=true
cargo lambda build --release --arm64 --output-format zip

# Add collector.yaml to the zip if it exists
if [ -f "collector.yaml" ]; then
    echo "Adding collector.yaml to Lambda package..."
    cd target/lambda/rust-scorer
    # Extract existing zip, add collector.yaml, and rezip
    unzip -q bootstrap.zip
    cp ../../../collector.yaml .
    zip -q bootstrap.zip collector.yaml
    cd ../../..
    echo "collector.yaml added to package"
fi

echo "Build complete!"
echo "Zip artifact location: target/lambda/rust-scorer/bootstrap.zip"
