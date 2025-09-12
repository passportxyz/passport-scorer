# 📚 Project Knowledge Map

## 🏗️ Architecture

- @architecture/scoring_flow.md - V2 API scoring endpoint flow, event recording, Rust migration complete

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

## 🔌 API

- @api/authentication.md - API key PBKDF2-SHA256 hashing and field types
- @api/human_points.md - Complete points tracking implementation and Rust specifics
- @api/axum_routing.md - Axum 0.8 route parameter syntax changes
- @api/database_signatures.md - Database operation signature alignment
- @api/error_handling.md - HTTP status code mapping

## 💾 Database

- @database/field_types.md - Correct BIGINT and VARCHAR types for Django tables
- @database/scorer_tables.md - BinaryWeightedScorer vs WeightedScorer dual table support

## 📦 Dependencies

- @dependencies/didkit.md - Credential validation library

## ⚙️ Configuration

- @config/database.md - Django connections and pooling settings

## 🔄 Workflows

- @workflows/rust_testing.md - Test organization and database setup

## 🚀 Deployment

- @deployment/lambda_infrastructure.md - Pulumi-based Lambda deployment with ALB integration

## 🛠️ Tools

- @tools/log_analyzer.md - Rust tracing log performance analyzer with flame charts