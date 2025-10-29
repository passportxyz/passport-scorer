# 📚 Project Knowledge Map

## 🏗️ Architecture

- @architecture/scoring_flow.md - V2 API scoring endpoint flow, event recording, Rust migration complete
- @architecture/partner_dashboards.md - Dashboard discovery system and TopNav integration

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

## 🔌 API

- @api/authentication.md - API key PBKDF2-SHA256 hashing and field types
- @api/human_points.md - Complete points tracking implementation and Rust specifics
- @api/axum_routing.md - Axum 0.8 route parameter syntax changes
- @api/database_signatures.md - Database operation signature alignment
- @api/error_handling.md - HTTP status code mapping
- @api/api_key_performance_optimization.md - SHA-256 fast path implementation in Python and Rust
- @api/topnav_dashboard_discovery.md - Dashboard discovery API for TopNav component

## 💾 Database

- @database/field_types.md - Correct BIGINT and VARCHAR types for Django tables
- @database/scorer_tables.md - BinaryWeightedScorer vs WeightedScorer dual table support

## 📦 Dependencies

- @dependencies/didkit.md - Credential validation library

## ⚙️ Configuration

- @config/database.md - Django connections and pooling settings
- @config/opentelemetry.md - ADOT Lambda layer sidecar, endpoint configuration, JSON logging

## 🔄 Workflows

- @workflows/rust_testing.md - Test organization and database setup

## 🚀 Deployment

- @deployment/lambda_infrastructure.md - Pulumi-based Lambda deployment with ALB integration