# 📚 Project Knowledge Map

## 🏗️ Architecture

- @architecture/scoring_flow.md - V2 API scoring endpoint flow, event recording, Rust migration complete
- @architecture/partner_dashboards.md - Dashboard discovery system and TopNav integration
- @architecture/api_endpoint_map.md - Complete map of all scoring-related endpoints and Lambda functions
- @architecture/ceramic_cache_scoring.md - Integration points and migration strategy
- @architecture/rust_scorer_implementation_status.md - Complete status of all 15 endpoints, architecture patterns, performance targets
- @architecture/rust_scorer_clean_architecture.md - Three-layer architecture pattern with domain-driven design

## 🎨 Patterns

- @patterns/deduplication.md - LIFO retry logic and provider-based stamp deduplication

## ⚠️ Gotchas

- @gotchas/nullifier_handling.md - Python feature flags vs Rust simplifications for nullifiers
- @gotchas/event_data_structure.md - Score update event serialization format
- @gotchas/django_model_discrepancies.md - Confirmed Django table schema without timestamps
- @gotchas/score_calculation.md - Score calculation details, provider dedup, decimal precision
- @gotchas/type_conversions.md - Module boundary type conversions required
- @gotchas/scorer_id_confusion.md - API scorer_id vs database community_id naming
- @gotchas/human_points_provider_handling.md - Django CharField NULL vs empty string conversion
- @gotchas/performance_analysis.md - Flamegraphs vs distributed tracing for I/O-bound services
- @gotchas/trusted_iam_issuers.md - Environment variable loading with OnceLock caching
- @gotchas/api_key_hashing_performance.md - PBKDF2 performance problem and solution
- @gotchas/django_conn_max_age_lambda.md - Connection management issues with Lambda and RDS Proxy
- @gotchas/ceramic_cache_v2_never_implemented.md - V1 stamps only, V2 was abandoned
- @gotchas/alb_listener_priority.md - Priority ordering for header-based routing
- @gotchas/target_group_alb_limitation.md - Cannot span multiple load balancers
- @gotchas/container_environment_detection.md - PostgreSQL startup in containers vs systems
- @gotchas/didkit_eip712_signing.md - TypedData structure and @context requirements

## 🔌 API

- @api/authentication.md - API key PBKDF2-SHA256 hashing and field types
- @api/human_points.md - Complete points tracking implementation and Rust specifics
- @api/axum_routing.md - Axum 0.8 route parameter syntax changes
- @api/database_signatures.md - Database operation signature alignment
- @api/error_handling.md - HTTP status code mapping
- @api/api_key_performance_optimization.md - SHA-256 fast path implementation in Python and Rust
- @api/topnav_dashboard_discovery.md - Dashboard discovery API for TopNav component
- @api/internal_api_endpoints.md - Complete inventory of 12 internal endpoints with SQL queries
- @api/cgrants_endpoint.md - Detailed contributor statistics endpoint documentation
- @api/addstamps_payload_flexibility.md - scorer_id type handling

## 💾 Database

- @database/field_types.md - Correct BIGINT and VARCHAR types for Django tables
- @database/scorer_tables.md - BinaryWeightedScorer vs WeightedScorer dual table support
- @database/internal_api_schema.md - Tables and performance notes for internal endpoints

## 📦 Dependencies

- @dependencies/didkit.md - Credential validation library

## ⚙️ Configuration

- @config/database.md - Django connections and pooling settings
- @config/opentelemetry.md - ADOT Lambda layer sidecar, endpoint configuration, JSON logging

## 🔄 Workflows

- @workflows/rust_testing.md - Test organization and database setup
- @workflows/development_setup.md - Modular setup scripts and SQLX requirements
- @workflows/comparison_testing.md - Python/Rust response validation infrastructure

## 🚀 Deployment

- @deployment/lambda_infrastructure.md - Pulumi-based Lambda deployment with ALB integration

## 🎯 Performance

- @performance/embed_lambda_issues.md - Cold start and RDS Proxy connection acquisition problems
