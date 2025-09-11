# Rust Scorer Lambda Deployment Guide

## Overview
This guide covers deploying the Rust scorer as an AWS Lambda function alongside the existing Python implementation.

## Architecture
- **Runtime**: ARM64 (Graviton2) for 34% better price/performance
- **Container**: Docker image in ECR (matches existing infrastructure)
- **Routing**: Header-based routing with `X-Use-Rust-Scorer: true`
- **Integration**: lambda_web bridges Lambda events to Axum HTTP

## Build & Deploy Process

### 1. Local Build
```bash
cd rust-scorer
./build-lambda.sh
```

This script:
- Installs cargo-lambda if needed
- Builds for ARM64 architecture
- Creates Docker container image

### 2. Push to ECR
```bash
# Get ECR login token
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com

# Tag the image
docker tag rust-scorer-lambda:latest \
  <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/passport-scorer:rust-latest

# Push to ECR
docker push <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/passport-scorer:rust-latest
```

### 3. Deploy with Pulumi
```bash
cd infra/aws

# Set the Rust image tag (optional, defaults to "rust-latest")
export RUST_DOCKER_IMAGE_TAG=rust-v1.0.0

# Deploy to staging
pulumi up --stack staging
```

## Testing

### Local Testing with Docker
```bash
# Run the Lambda container locally
docker run -p 9000:8080 \
  -e DATABASE_URL=postgresql://... \
  rust-scorer-lambda:latest

# Test with curl
curl -X GET \
  http://localhost:9000/2015-03-31/functions/function/invocations \
  -d '{"path": "/v2/stamps/1/score/0x123...", "httpMethod": "GET"}'
```

### Testing in AWS

#### With Header Routing
```bash
# This goes to Rust Lambda
curl -H "X-Use-Rust-Scorer: true" \
  https://api.passport.xyz/v2/stamps/1/score/0x123...

# This goes to Python Lambda (default)
curl https://api.passport.xyz/v2/stamps/1/score/0x123...
```

## Deployment Strategy

### Phase 1: Header-Based Testing (Current)
- Deploy Rust Lambda with header-based routing
- Only requests with `X-Use-Rust-Scorer: true` use Rust
- Monitor performance and accuracy

### Phase 2: Weighted Rollout (Future)
```typescript
// In infra/aws/v2/rust-scorer.ts
// Uncomment the weighted routing section to enable:
// - 5% traffic → Rust
// - 95% traffic → Python
// With session affinity for consistent user experience
```

### Phase 3: Full Migration
- Remove header condition
- Route 100% traffic to Rust
- Keep Python as backup

## Environment Variables

The Lambda inherits all environment variables from Python deployment:
- `RDS_PROXY_URL` - Database connection via RDS Proxy
- `HUMAN_POINTS_*` - Human points configuration
- All secrets from AWS Secrets Manager

## Monitoring

### CloudWatch Logs
```bash
aws logs tail /aws/lambda/passport-v2-rust-scorer --follow
```

### Metrics to Watch
- Cold start time (target: <100ms)
- P50 latency (target: <100ms)
- P99 latency (target: <500ms)
- Memory usage (should be <256MB)
- Error rate (should match Python baseline)

## Rollback Plan

If issues arise:
1. **Immediate**: Remove `X-Use-Rust-Scorer` header from client requests
2. **Infrastructure**: Set listener rule priority higher than Rust (e.g., 98 vs 99)
3. **Full rollback**: Comment out Rust Lambda in Pulumi and redeploy

## Performance Benefits

### Why ARM64/Graviton2?
- **34% better price/performance** vs x86
- **20% cheaper** duration charges
- **19% better performance** for compute-intensive workloads
- **Lower cold starts** - Rust + ARM64 = fastest Lambda configuration

### Expected Improvements vs Python
- **10x faster** P50 latency (100ms vs 1000ms)
- **4x faster** P99 latency (500ms vs 2000ms)
- **50x faster** cold starts (100ms vs 5 seconds)
- **10x lower** memory usage (256MB vs 2GB+)

## Troubleshooting

### Build Issues
```bash
# Clear cargo cache if build fails
cargo clean
rm -rf target/

# Ensure Docker buildx is available for ARM64
docker buildx create --use
docker buildx inspect --bootstrap
```

### Lambda Timeout
- Default timeout is 30 seconds
- Adjust in `infra/aws/v2/rust-scorer.ts` if needed

### Database Connection
- Ensure `RDS_PROXY_URL` is set correctly
- Lambda must be in VPC with access to RDS Proxy
- Security groups must allow connection

## Next Steps

1. Build and push Docker image to ECR
2. Deploy with Pulumi to staging
3. Test with header-based routing
4. Monitor metrics for 24 hours
5. Gradually increase traffic percentage
6. Full production rollout once validated