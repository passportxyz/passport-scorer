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

## 🔌 API

- @api/authentication.md - API key mechanism and permissions
- @api/human_points.md - Complete points tracking implementation and Rust specifics
- @api/axum_routing.md - Axum 0.8 route parameter syntax changes
- @api/database_signatures.md - Database operation signature alignment
- @api/error_handling.md - HTTP status code mapping

## 📦 Dependencies

- @dependencies/didkit.md - Credential validation library

## ⚙️ Configuration

- @config/database.md - Django connections and pooling settings

## 🔄 Workflows

- @workflows/rust_testing.md - Test organization and database setup

## 🚀 Deployment

- @deployment/lambda_infrastructure.md - Pulumi-based Lambda deployment with ALB integration