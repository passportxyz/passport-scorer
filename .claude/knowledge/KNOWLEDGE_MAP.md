# 📚 Project Knowledge Map

*Last updated: 2025-09-10*

## 🏗️ Architecture

- [Scoring Flow Architecture](architecture/scoring_flow.md) - V2 API scoring endpoint flow, event recording, Rust migration Phases 1-5 complete

## 🎨 Patterns

- [Deduplication Patterns](patterns/deduplication.md) - LIFO retry logic and provider-based stamp deduplication

## ⚠️ Gotchas

- [Nullifier Handling](gotchas/nullifier_handling.md) - Feature flags, array vs hash field, and Rust simplifications
- [Event Data Structure](gotchas/event_data_structure.md) - Score update event serialization format
- [Django Model Discrepancies](gotchas/django_model_discrepancies.md) - Field mismatches between Rust models and actual Django models
- [Score Calculation](gotchas/score_calculation.md) - Phase 5 implementation details, provider dedup, decimal precision

## 🔌 API

- [Authentication](api/authentication.md) - API key mechanism, djangorestframework-api-key v2 hashing, and Rust implementation
- [Human Points System](api/human_points.md) - Complete points tracking implementation

## 📦 Dependencies

- [DIDKit](dependencies/didkit.md) - Credential validation library

## ⚙️ Configuration

- [Database Configuration](config/database.md) - Django connections and pooling settings