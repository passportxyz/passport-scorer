# Lambda Infrastructure & Deployment

Infrastructure uses Pulumi (TypeScript) for Lambda creation, ALB integration, and weighted routing.

## Docker-Based Lambda Deployment

All Lambdas are container-based (not ZIP):
- Python Lambdas: Standard Docker images
- Rust Lambdas: ARM64 images with cargo-lambda (34% better price/performance than x86)
- Environment variables: Pulled from AWS Secrets Manager via Pulumi
- Monitoring: CloudWatch alarms with PagerDuty integration
- VPC: Private subnets with RDS Proxy for database connection pooling

## Core Problem: buildHttpLambdaFn Monolith

The `buildHttpLambdaFn()` function in `infra/lib/scorer/new_service.ts` does three things:
1. Creates Lambda function
2. Creates ALB target group
3. Creates ALB listener rule

This causes priority conflicts when trying to create weighted rules for dual implementations (Python + Rust). AWS ALB allows only ONE rule per priority number.

## Current Listener Rule Priorities (Updated Nov 24, 2025)

All priorities shifted to resolve PriorityInUse conflicts:

- **V2 API**: 2110-2112
  - 2110: Models score
  - 2112: Stamps score (weighted routing endpoint)

- **Ceramic Cache**: 1030-1039
  - 1031: Score POST (weighted routing)
  - 1032: Stamps bulk POST (weighted routing)
  - 1033: Stamps bulk PATCH (Python-only)
  - 1034: Stamps bulk DELETE (Python-only)
  - 1035: Stamp GET
  - 1036: Weights GET
  - 1037: Analysis GET

- **Embed**: 2104-2106
  - 2104: Stamps POST (weighted routing)
  - 2105: Validate API key GET (weighted routing)
  - 2106: Score GET (weighted routing)

## Weighted Routing Implementation

For endpoints with both Python and Rust implementations, one ALB listener rule with weighted forward config:

```typescript
{
  type: "forward",
  forwardConfig: {
    targetGroups: [
      { targetGroupArn: rustTarget.arn, weight: rustPercent },
      { targetGroupArn: pythonTarget.arn, weight: pythonPercent }
    ],
    targetGroupStickinessConfig: {
      enabled: true,
      durationSeconds: 3600  // 1 hour session stickiness
    }
  }
}
```

Environment-based percentages:
- **Staging/Review**: 100% Rust, 0% Python
- **Production**: 0% Rust, 100% Python (safe default)

## Lambda Function Locations

Python Lambdas:
- `api/v2/aws_lambdas/stamp_score_GET.py`: Main scoring
- `api/v2/aws_lambdas/models_score_GET.py`: Model analysis
- `api/embed/lambda_fn.py`: Embed endpoints (3 handlers)
- `api/aws_lambdas/scorer_api_passport/v1/`: Legacy v1 endpoints

Rust Lambda:
- `rust-scorer/src/main.rs`: Conditional lambda_http bridge
- `rust-scorer/Dockerfile.lambda`: ARM64 build
- `rust-scorer/build-lambda.sh`: Build script

## Pulumi Infrastructure

Infrastructure files:
- `infra/aws/v2/index.ts`: V2 API endpoints
- `infra/aws/index.ts`: Ceramic cache, embed, and other endpoints
- `infra/aws/v2/rust-scorer.ts`: Rust scorer weighted rules
- `infra/lib/scorer/new_service.ts`: buildHttpLambdaFn and utilities

Secrets Manager integration: Environment variables loaded at Pulumi synthesis time.

## Target Group Names

Well-known names for weighted routing lookups:
- `l-passport-v2-stamp-score` (Python v2 stamp score)
- `l-cc-v1-st-bulk-POST-0` (Python ceramic-cache stamps bulk POST)
- `l-cc-v1-score-POST-0` (Python ceramic-cache score POST)
- `embed-st-lambda-target-group` (Python embed stamps)
- `embed-rl-lambda-target-group` (Python embed rate limit)
- `embed-gs-lambda-target-group` (Python embed score)
- `l-passport-v2-rust-scorer` (Rust public ALB)
- `l-passport-v2-rust-scorer-int` (Rust internal ALB)

AWS doesn't allow same target group on multiple ALBs, so Rust uses separate groups for public and internal ALBs.

## Deployment Process

1. Build Rust image: `rust-scorer/build-lambda.sh`
2. Push to ECR with RUST_DOCKER_IMAGE_TAG
3. Run Pulumi: `pulumi up`
4. Monitor weighted routing percentages
5. Gradual rollout: 5% → 10% → 25% → 50% → 100%
6. Instant rollback: Set rust: 0, python: 100

## Performance Configuration

Lambda settings:
- Memory: 256MB (Rust), 256-1024MB (Python)
- Timeout: 60s (scoring), 90s (analysis)
- Cold start targets: <100ms (Rust) vs 2-5s (Python)

Connection pooling:
- Pool size: 5 connections (RDS Proxy handles pooling)
- No CONN_MAX_AGE: Django creates new connection per request
- close_old_connections() called at start of each Lambda handler

## Monitoring & Observability

CloudWatch metrics:
- TargetResponseTime
- HTTPCode_Target_4XX_Count
- HTTPCode_Target_5XX_Count
- Latency percentiles (P50, P95, P99)

OpenTelemetry:
- ADOT Lambda layer sidecar (handles all telemetry processing)
- Exports to Jaeger/X-Ray via OTLP (localhost:4318 HTTP)
- Spans include full request lifecycle

Alarms: PagerDuty integration for error thresholds
