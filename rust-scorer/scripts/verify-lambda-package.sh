#!/bin/bash
set -e

echo "🔍 Verifying Lambda package setup..."
echo

# Check if collector.yaml exists
if [ ! -f "collector.yaml" ]; then
    echo "❌ ERROR: collector.yaml not found in current directory"
    exit 1
fi
echo "✅ collector.yaml exists"

# Check if cargo-lambda is available
if ! command -v cargo-lambda &> /dev/null; then
    echo "⚠️  cargo-lambda not installed (needed for actual build)"
    echo "   Install with: cargo install cargo-lambda"
else
    echo "✅ cargo-lambda is installed"
fi

# Check if the deployment directory structure is correct
echo
echo "📁 Expected deployment structure:"
echo "   rust-scorer/collector.yaml ✓"
echo "   rust-scorer/build-lambda-zip.sh ✓"
echo "   rust-scorer-artifact/bootstrap.zip (created during build)"
echo "   infra/aws/index.ts (expects ../rust-scorer-artifact/bootstrap.zip)"

# If build artifacts exist, verify them
if [ -f "target/lambda/rust-scorer/bootstrap.zip" ]; then
    echo
    echo "📦 Checking existing build artifact..."
    if unzip -l target/lambda/rust-scorer/bootstrap.zip | grep -q collector.yaml; then
        echo "✅ collector.yaml is in the existing package"
    else
        echo "⚠️  collector.yaml is NOT in the existing package"
    fi
fi

if [ -f "../rust-scorer-artifact/bootstrap.zip" ]; then
    echo
    echo "📦 Checking deployment artifact..."
    if unzip -l ../rust-scorer-artifact/bootstrap.zip | grep -q collector.yaml; then
        echo "✅ collector.yaml is in the deployment package"
    else
        echo "⚠️  collector.yaml is NOT in the deployment package"
    fi
fi

echo
echo "💡 To build and package for Lambda deployment, run:"
echo "   ./build-lambda-zip.sh"
echo
echo "📝 The build script will:"
echo "   1. Build the Rust binary for ARM64 Lambda"
echo "   2. Package bootstrap binary + collector.yaml into zip"
echo "   3. Copy to ../rust-scorer-artifact/ for Pulumi deployment"