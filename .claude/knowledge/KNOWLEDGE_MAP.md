# 📚 Project Knowledge Map

*Last updated: 2025-11-13*

## 🏗️ Architecture

- [Scoring Flow Architecture](architecture/scoring_flow.md) - V2 API scoring endpoint flow, event recording, Rust migration Phases 1-7 complete

## 🎨 Patterns

- [Deduplication Patterns](patterns/deduplication.md) - LIFO retry logic and provider-based stamp deduplication

## ⚠️ Gotchas

- [Nullifier Handling](gotchas/nullifier_handling.md) - Feature flags, array vs hash field, and Rust simplifications
- [Event Data Structure](gotchas/event_data_structure.md) - Score update event serialization format
- [Django Model Discrepancies](gotchas/django_model_discrepancies.md) - Field mismatches between Rust models and actual Django models
- [Score Calculation](gotchas/score_calculation.md) - Phase 5 implementation details, provider dedup, decimal precision
- [Type Conversions](gotchas/type_conversions.md) - Module boundary type conversions required in Phase 7

## 🔌 API

- [Authentication](api/authentication.md) - API key mechanism and permissions
- [Human Points](api/human_points.md) - Complete points tracking implementation
- [Axum Routing](api/axum_routing.md) - Axum 0.8 route parameter syntax changes
- [Phase 7 Function Signatures](api/phase7_signatures.md) - Database operation signature alignment
- [Error Handling](api/error_handling.md) - HTTP status code mapping

## 📦 Dependencies

- [DIDKit](dependencies/didkit.md) - Credential validation library

## ⚙️ Configuration

- [Database](config/database.md) - Django connections and pooling settings

## 🔄 Workflows

- [Rust Testing](workflows/rust_testing.md) - Test organization and database setup