# 📚 Project Knowledge Map

## 🏗️ Architecture

- @architecture/scoring_flow.md - V2 API scoring endpoint flow, event recording, Rust migration Phases 1-5 complete

## 🎨 Patterns

- @patterns/deduplication.md - LIFO retry logic and provider-based stamp deduplication

## ⚠️ Gotchas

- @gotchas/nullifier_handling.md - Feature flags, array vs hash field, and Rust simplifications
- @gotchas/event_data_structure.md - Score update event serialization format
- @gotchas/django_model_discrepancies.md - Field mismatches between Rust models and actual Django models
- @gotchas/score_calculation.md - Phase 5 implementation details, provider dedup, decimal precision

## 🔌 API

- @api/authentication.md - API key mechanism and permissions
- @api/human_points.md - Complete points tracking implementation

## 📦 Dependencies

- @dependencies/didkit.md - Credential validation library

## ⚙️ Configuration

- @config/database.md - Django connections and pooling settings