# Lambda Deployment Infrastructure

## Existing Infrastructure

The project already uses Pulumi (TypeScript) for Lambda deployments with a sophisticated setup:

1. **Docker-based Lambda functions** with custom images
2. **ALB integration** with target groups and listener rules
3. **buildHttpLambdaFn utility** that creates Lambda + ALB target group + listener rule
4. **V2 API** already has Lambda handlers for scoring endpoints
5. **Environment variables** pulled from AWS Secrets Manager via Pulumi
6. **Monitoring** with CloudWatch alarms and PagerDuty integration
7. **VPC** with private subnets and security groups
8. **Python Lambda handlers** in api/v2/aws_lambdas/

## Rust Lambda Deployment

Completed Lambda deployment infrastructure for Rust scorer:

### Implementation Details

1. **Lambda handler** with conditional compilation for lambda_web bridge
2. **ARM64 Docker container** with cargo-lambda for 34% better price/performance
3. **Pulumi infrastructure** with header-based routing (X-Use-Rust-Scorer: true)
4. **Build pipeline scripts** and deployment documentation
5. **Integration** with existing ALB, VPC, RDS Proxy, and secrets
6. **ADOT Lambda layer** for OpenTelemetry sidecar telemetry processing

### Key Architectural Decisions

- **Container deployment** to match existing Python infrastructure
- **ARM64/Graviton2** for cost and performance benefits
- **Header-based routing** for safe testing (priority 99)
- **Separate Docker tag** (RUST_DOCKER_IMAGE_TAG) for independent deployment
- **Weighted routing strategy** documented for future gradual rollout

### Performance Targets

- Cold start <100ms (vs Python 2-5s)
- P50 <100ms, P95 <200ms, P99 <500ms
- Memory <256MB

### Related Files

- `infra/aws/index.ts`, `infra/aws/v2/index.ts` - Pulumi infrastructure
- `infra/lib/scorer/new_service.ts` - Build utilities
- `api/v2/aws_lambdas/stamp_score_GET.py` - Python Lambda handler
- `rust-scorer/Dockerfile.lambda` - Rust Lambda container
- `rust-scorer/build-lambda.sh` - Build script
- `rust-scorer/src/main.rs` - Lambda handler code
- `infra/aws/v2/rust-scorer.ts` - Rust-specific infrastructure
- `rust-scorer/LAMBDA_DEPLOYMENT.md` - Deployment documentation
- `RUST_MIGRATION_PLAN.md` - Overall migration plan