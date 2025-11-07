# 📚 Project Knowledge Map

## 🏗️ Architecture

- [Scoring Flow Architecture](architecture/scoring_flow.md) - V2 API scoring endpoint flow, event recording, Rust migration complete
- [Partner Dashboards](architecture/partner_dashboards.md) - Dashboard discovery system and TopNav integration *(Updated: 2025-10-29)*

## 🎨 Patterns

- [Deduplication Patterns](patterns/deduplication.md) - LIFO retry logic and provider-based stamp deduplication

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
- [API Key Hashing Performance](gotchas/api_key_hashing_performance.md) - PBKDF2 performance problem and solution *(Updated: 2025-10-16)*

## 🔌 API

- [Authentication](api/authentication.md) - API key PBKDF2-SHA256 hashing and field types
- [Human Points](api/human_points.md) - Complete points tracking implementation and Rust specifics
- [Axum Routing](api/axum_routing.md) - Axum 0.8 route parameter syntax changes
- [Database Signatures](api/database_signatures.md) - Database operation signature alignment
- [Error Handling](api/error_handling.md) - HTTP status code mapping
- [API Key Performance Optimization](api/api_key_performance_optimization.md) - SHA-256 fast path implementation in Python and Rust *(Updated: 2025-10-16)*
- [TopNav Dashboard Discovery](api/topnav_dashboard_discovery.md) - Dashboard discovery API for TopNav component *(Updated: 2025-10-29)*

## 💾 Database

- [Field Types](database/field_types.md) - Correct BIGINT and VARCHAR types for Django tables
- [Scorer Tables](database/scorer_tables.md) - BinaryWeightedScorer vs WeightedScorer dual table support

## 📦 Dependencies

- [DIDKit](dependencies/didkit.md) - Credential validation library

## ⚙️ Configuration

- [Database](config/database.md) - Django connections and pooling settings
- [OpenTelemetry](config/opentelemetry.md) - ADOT Lambda layer sidecar, endpoint configuration, JSON logging

## 🔄 Workflows

- [Rust Testing](workflows/rust_testing.md) - Test organization and database setup

## 🚀 Deployment

- [Lambda Infrastructure](deployment/lambda_infrastructure.md) - Pulumi-based Lambda deployment with ALB integration