#!/bin/bash
set -e

echo "Building Rust Lambda for ARM64..."

# Install cargo-lambda if not present
if ! command -v cargo-lambda &> /dev/null; then
    echo "Installing cargo-lambda..."
    cargo install cargo-lambda
fi

# Build for ARM64
echo "Building with cargo-lambda..."
cargo lambda build --release --arm64 --features lambda

# Build Docker image
echo "Building Docker image..."
docker buildx build \
    --platform linux/arm64 \
    -f Dockerfile.lambda \
    -t rust-scorer-lambda:latest \
    .

echo "Build complete!"
echo ""
echo "To test locally:"
echo "  docker run -p 9000:8080 rust-scorer-lambda:latest"
echo ""
echo "To push to ECR:"
echo "  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com"
echo "  docker tag rust-scorer-lambda:latest <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/passport-scorer:rust-latest"
echo "  docker push <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/passport-scorer:rust-latest"