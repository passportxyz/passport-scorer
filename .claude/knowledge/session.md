### [16:50] [deployment] Existing Lambda deployment infrastructure
**Details**: The project already uses Pulumi (TypeScript) for Lambda deployments with a sophisticated setup:
1. Docker-based Lambda functions with custom images
2. ALB integration with target groups and listener rules
3. buildHttpLambdaFn utility that creates Lambda + ALB target group + listener rule
4. V2 API already has Lambda handlers for scoring endpoints
5. Environment variables pulled from AWS Secrets Manager via Pulumi
6. Monitoring with CloudWatch alarms and PagerDuty integration
7. VPC with private subnets and security groups
8. Existing Python Lambda handlers in api/v2/aws_lambdas/
**Files**: infra/aws/index.ts, infra/aws/v2/index.ts, infra/lib/scorer/new_service.ts, api/v2/aws_lambdas/stamp_score_GET.py
---

### [17:53] [deployment] Phase 8 Lambda deployment complete
**Details**: Phase 8 of Rust migration completed on November 14, 2024. Created complete Lambda deployment infrastructure:
1. Lambda handler with conditional compilation for lambda_web bridge
2. ARM64 Docker container with cargo-lambda for 34% better price/performance
3. Pulumi infrastructure with header-based routing (X-Use-Rust-Scorer: true)
4. Build pipeline scripts and deployment documentation
5. Integration with existing ALB, VPC, RDS Proxy, and secrets

Key decisions:
- Container deployment to match existing Python infrastructure
- ARM64/Graviton2 for cost and performance benefits
- Header-based routing for safe testing (priority 99)
- Separate Docker tag (RUST_DOCKER_IMAGE_TAG) for independent deployment
- Weighted routing strategy documented for future gradual rollout

Ready for Phase 9 performance testing with targets:
- Cold start <100ms (vs Python 2-5s)
- P50 <100ms, P95 <200ms, P99 <500ms
- Memory <256MB
**Files**: rust-scorer/Dockerfile.lambda, rust-scorer/build-lambda.sh, rust-scorer/src/main.rs, infra/aws/v2/rust-scorer.ts, rust-scorer/LAMBDA_DEPLOYMENT.md, RUST_MIGRATION_PLAN.md
---

