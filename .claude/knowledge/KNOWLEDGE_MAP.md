# 📚 Project Knowledge Map

## 🏗️ Architecture

- [Scoring Flow Architecture](architecture/scoring_flow.md) - V2 API scoring endpoint flow, event recording, Rust migration complete
- [Partner Dashboards](architecture/partner_dashboards.md) - Dashboard discovery system and TopNav integration *(Updated: 2025-10-29)*
- [API Endpoint Map](architecture/api_endpoint_map.md) - Complete map of all scoring-related endpoints and Lambda functions *(Added: 2025-11-14)*
- [Ceramic Cache Scoring](architecture/ceramic_cache_scoring.md) - Integration points and migration strategy *(Added: 2025-11-14)*
- [Rust Scorer Implementation Status](architecture/rust_scorer_implementation_status.md) - Complete status of all 15 endpoints, architecture patterns, performance targets *(Added: 2025-11-20)*
- [Lambda Infrastructure Analysis](architecture/lambda_infrastructure_analysis.md) - Comprehensive AWS Lambda creation patterns and routing architecture *(Added: 2025-11-24)*
- [Embed Stamp Customization](architecture/embed_stamp_customization.md) - Customizable stamp sections for Embed product with PlatformMetadata *(Added: 2026-02-10)*
- [Custom Stamps Frontend Integration](architecture/custom_stamps_frontend.md) - Custom stamps data flow, provider ID generation, frontend consumption *(Added: 2026-02-10)*

### Local Knowledge
- rust-scorer/.knowledge/architecture.md - Three-layer architecture pattern (relocated from global)

## 🎨 Patterns

- [Deduplication Patterns](patterns/deduplication.md) - LIFO retry logic and provider-based stamp deduplication
- [Django Model Patterns](patterns/django_model_patterns.md) - Enum choices, BooleanField migrations, admin inlines, JSONField validation *(Added: 2026-02-10)*
- [Custom Credential System](patterns/custom_credential_system.md) - Three-model architecture for extensible credential types *(Added: 2026-02-10)*

### Local Knowledge
- rust-scorer/.knowledge/code-organization.md - Code structure, duplication issues (relocated from global)

## ⚠️ Gotchas

- [Nullifier Handling](gotchas/nullifier_handling.md) - Python feature flags vs Rust simplifications for nullifiers
- [Event Data Structure](gotchas/event_data_structure.md) - Score update event serialization format
- [Django Model Discrepancies](gotchas/django_model_discrepancies.md) - Confirmed Django table schema without timestamps
- [Score Calculation](gotchas/score_calculation.md) - Score calculation details, provider dedup, decimal precision
- [Type Conversions](gotchas/type_conversions.md) - Module boundary type conversions required
- [Scorer ID Confusion](gotchas/scorer_id_confusion.md) - API scorer_id vs database community_id naming
- [Human Points Provider Handling](gotchas/human_points_provider_handling.md) - Django CharField NULL vs empty string conversion
- [Performance Analysis](gotchas/performance_analysis.md) - Flamegraphs vs distributed tracing for I/O-bound services
- [TRUSTED_IAM_ISSUERS Configuration](gotchas/trusted_iam_issuers.md) - Environment variable loading with OnceLock caching
- [Django CONN_MAX_AGE Lambda](gotchas/django_conn_max_age_lambda.md) - Connection management issues with Lambda and RDS Proxy *(Added: 2025-11-14)*
- [Ceramic Cache V2 Never Implemented](gotchas/ceramic_cache_v2_never_implemented.md) - V1 stamps only, V2 was abandoned *(Added: 2025-11-14)*
- [ALB Listener Priority](gotchas/alb_listener_priority.md) - Priority ordering for header-based routing *(Added: 2025-11-20)*
- [Target Group ALB Limitation](gotchas/target_group_alb_limitation.md) - Cannot span multiple load balancers *(Added: 2025-11-20)*
- [DIDKit EIP-712 Signing](gotchas/didkit_eip712_signing.md) - TypedData structure and @context requirements *(Added: 2025-11-20)*
- [ALB Listener Rules Conflicts](gotchas/alb_listener_rules_conflicts.md) - Priority conflicts and infrastructure refactoring *(Updated: 2025-11-24)*
- [Django Migrations](gotchas/django_migrations.md) - Out of sync migrations and --run-syncdb fix *(Added: 2025-11-24)*
- [PostgreSQL gexec](gotchas/postgresql_gexec.md) - Database creation with gexec gotchas *(Added: 2025-11-24)*
- [WeightConfiguration CSV](gotchas/weight_configuration_csv.md) - Optional CSV field handling in Django admin *(Added: 2025-11-24)*
- [Database Query Performance](gotchas/database_query_performance.md) - LOWER() breaks indexes in WHERE clauses *(Added: 2025-11-24)*
- [Custom Platform Bugs](gotchas/custom_platform_bugs.md) - search_display typo and hardcoded isEVM=False *(Added: 2026-02-10)*
- [Rust Scorer Missing Custom Weights](gotchas/rust_scorer_missing_custom_weights.md) - Customization dynamic weights not merged in Rust *(Added: 2026-02-10)*
- [Django AddField PostgreSQL](gotchas/django_addfield_postgresql.md) - BooleanField AddField is zero-downtime on PG11+ *(Added: 2026-02-10)*

### Local Knowledge
- dev-setup/.knowledge/environment-detection.md - PostgreSQL startup detection (relocated from global)

## 🔌 API

- [Authentication](api/authentication.md) - API key PBKDF2-SHA256 hashing and field types
- [Human Points](api/human_points.md) - Complete points tracking implementation and Rust specifics
- [Axum Routing](api/axum_routing.md) - Axum 0.8 route parameter syntax changes
- [Database Signatures](api/database_signatures.md) - Database operation signature alignment
- [Error Handling](api/error_handling.md) - HTTP status code mapping
- [API Key Performance Optimization](api/api_key_performance_optimization.md) - SHA-256 fast path implementation in Python and Rust *(Updated: 2025-10-16)*
- [TopNav Dashboard Discovery](api/topnav_dashboard_discovery.md) - Dashboard discovery API for TopNav component *(Updated: 2025-10-29)*
- [Internal API Endpoints](api/internal_api_endpoints.md) - Complete inventory of 12 internal endpoints with SQL queries *(Added: 2025-11-20)*
- [CGrants Endpoint](api/cgrants_endpoint.md) - Detailed contributor statistics endpoint documentation *(Added: 2025-11-20)*
- [CORS Support](api/cors_support.md) - CORS configuration for ceramic cache endpoints *(Added: 2025-11-24)*

## 💾 Database

- [Field Types](database/field_types.md) - Correct BIGINT and VARCHAR types for Django tables
- [Scorer Tables](database/scorer_tables.md) - BinaryWeightedScorer vs WeightedScorer dual table support
- [Internal API Schema](database/internal_api_schema.md) - Tables and performance notes for internal endpoints *(Added: 2025-11-20)*

## 📦 Dependencies

- [DIDKit](dependencies/didkit.md) - Credential validation library
- [Valkey/Redis](dependencies/valkey_redis.md) - Redis/Valkey requirement for Django caching in development *(Added: 2026-02-10)*

## ⚙️ Configuration

- [Database](config/database.md) - Django connections and pooling settings
- [OpenTelemetry](config/opentelemetry.md) - ADOT Lambda layer sidecar, endpoint configuration, JSON logging

## 🔄 Workflows

- [Container Dev Setup](workflows/container_dev_setup.md) - Ubuntu/container setup scripts with micromamba, environment detection *(Added: 2026-02-11)*

### Local Knowledge
- rust-scorer/.knowledge/testing.md - Test organization (relocated from global)
- dev-setup/.knowledge/setup-guide.md - Modular setup scripts (relocated from global)
- rust-scorer/comparison-tests/.knowledge/testing-guide.md - Python/Rust validation (relocated from global)

## 🚀 Deployment

- [Lambda Infrastructure](deployment/lambda_infrastructure.md) - Pulumi-based Lambda deployment with ALB integration
- [Weighted Routing](deployment/weighted_routing.md) - Percentage-based load balancing for gradual Rust rollout *(Updated: 2025-11-24)*

## 🎯 Performance

- [Embed Lambda Issues](performance/embed_lambda_issues.md) - Cold start and RDS Proxy connection acquisition problems *(Added: 2025-11-14)*
