# 📚 Project Knowledge Map

*Last updated: 2025-09-10*

## 🏗️ Architecture

- [Scoring Flow Architecture](architecture/scoring_flow.md) - V2 API scoring endpoint flow, event recording, and Rust migration requirements

## 🎨 Patterns

- [Deduplication Patterns](patterns/deduplication.md) - LIFO retry logic and provider-based stamp deduplication

## ⚠️ Gotchas

- [Nullifier Handling](gotchas/nullifier_handling.md) - Feature flags, array vs hash field, and Rust simplifications
- [Event Data Structure](gotchas/event_data_structure.md) - Score update event serialization format

## 🔌 API

- [Authentication](api/authentication.md) - API key mechanism and permissions
- [Human Points System](api/human_points.md) - Complete points tracking implementation

## 📦 Dependencies

- [DIDKit](dependencies/didkit.md) - Credential validation library

## ⚙️ Configuration

- [Database Configuration](config/database.md) - Django connections and pooling settings