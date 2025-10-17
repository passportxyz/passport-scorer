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
    cd target/lambda/passport-scorer
    # Extract existing zip, add collector.yaml, and rezip
    unzip -q -o bootstrap.zip
    cp -f ../../../collector.yaml .
    # Remove old zip and create new one with all files
    rm -f bootstrap.zip
    zip -q -r bootstrap.zip bootstrap collector.yaml
    cd ../../..
    echo "collector.yaml added to package"
fi

echo "Build complete!"
echo "Zip artifact location: target/lambda/passport-scorer/bootstrap.zip"

# Verify collector.yaml is in the package
echo "Verifying package contents..."
if unzip -l target/lambda/passport-scorer/bootstrap.zip | grep -q collector.yaml; then
    echo "✅ collector.yaml is in the package"
else
    echo "❌ WARNING: collector.yaml is NOT in the package!"
    exit 1
fi

# Copy to deployment location expected by Pulumi
echo "Copying to deployment location..."
mkdir -p ../rust-scorer-artifact
cp target/lambda/passport-scorer/bootstrap.zip ../rust-scorer-artifact/
echo "Deployment artifact ready at: ../rust-scorer-artifact/bootstrap.zip"
