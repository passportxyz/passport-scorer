# 📚 Project Knowledge Map

## 🏗️ Architecture

- @architecture/scoring_flow.md - V2 API scoring endpoint flow, event recording, Rust migration Phases 1-7 complete

## 🎨 Patterns

- @patterns/deduplication.md - LIFO retry logic and provider-based stamp deduplication

## ⚠️ Gotchas

- @gotchas/nullifier_handling.md - Feature flags, array vs hash field, and Rust simplifications
- @gotchas/event_data_structure.md - Score update event serialization format
- @gotchas/django_model_discrepancies.md - Field mismatches between Rust models and actual Django models
- @gotchas/score_calculation.md - Phase 5 implementation details, provider dedup, decimal precision
- @gotchas/type_conversions.md - Module boundary type conversions required in Phase 7

## 🔌 API

- @api/authentication.md - API key mechanism and permissions
- @api/human_points.md - Complete points tracking implementation
- @api/axum_routing.md - Axum 0.8 route parameter syntax changes
- @api/phase7_signatures.md - Database operation signature alignment
- @api/error_handling.md - HTTP status code mapping

## 📦 Dependencies

- @dependencies/didkit.md - Credential validation library

## ⚙️ Configuration

- @config/database.md - Django connections and pooling settings

## 🔄 Workflows

- @workflows/rust_testing.md - Test organization and database setup