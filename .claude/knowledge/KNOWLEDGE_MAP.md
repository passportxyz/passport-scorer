# 📚 Project Knowledge Map

*Last updated: 2025-09-12*

## 🏗️ Architecture

- [Scoring Flow Architecture](architecture/scoring_flow.md) - V2 API scoring endpoint flow, event recording, Rust migration complete

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

## 🔌 API

- [Authentication](api/authentication.md) - API key PBKDF2-SHA256 hashing and field types
- [Human Points](api/human_points.md) - Complete points tracking implementation and Rust specifics
- [Axum Routing](api/axum_routing.md) - Axum 0.8 route parameter syntax changes
- [Database Signatures](api/database_signatures.md) - Database operation signature alignment
- [Error Handling](api/error_handling.md) - HTTP status code mapping

## 💾 Database

- [Field Types](database/field_types.md) - Correct BIGINT and VARCHAR types for Django tables
- [Scorer Tables](database/scorer_tables.md) - BinaryWeightedScorer vs WeightedScorer dual table support

## 📦 Dependencies

- [DIDKit](dependencies/didkit.md) - Credential validation library

## ⚙️ Configuration

- [Database](config/database.md) - Django connections and pooling settings

## 🔄 Workflows

- [Rust Testing](workflows/rust_testing.md) - Test organization and database setup

## 🚀 Deployment

- [Lambda Infrastructure](deployment/lambda_infrastructure.md) - Pulumi-based Lambda deployment with ALB integration