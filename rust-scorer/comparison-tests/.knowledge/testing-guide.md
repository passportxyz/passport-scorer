# Comparison Test Infrastructure for Python/Rust Migration

## Overview

Comparison-tests infrastructure in `rust-scorer/comparison-tests/` validates Python/Rust response equivalence.

## Features

- Auto-loads `.env.development` using dotenvy (standard format, no export/shell vars)
- Starts both Python (8002) and Rust (3000) servers
- Compares JSON responses with sorted keys
- All 13/13 tests passing (as of Nov 2025)

## Key Requirements Discovered

### Configuration
- Scorer type must be 'WEIGHTED_BINARY' not 'BinaryWeightedScorer'
- CERAMIC_CACHE_SCORER_ID required in env
- DATABASE_URL needs `?sslmode=disable` for local PostgreSQL
- Redis/Valkey required for Django caching

### Test Categories

1. **Simple GET endpoints** (weights, allow-list) - ✓ Complete
2. **Scoring endpoints** with valid credentials, API key auth - ✓ Complete
3. **POST endpoints** (bans, revocations, add stamps) - ✓ Complete
4. **Complex endpoints** (cgrants statistics) - ✓ Complete

## Testing Strategy

- Unit tests for each query function
- Integration tests against test database
- Shadow traffic before cutover
- Validation checklist for response compatibility

## Files

- `rust-scorer/comparison-tests/src/main.rs` - Test runner
- `rust-scorer/comparison-tests/HANDOFF.md` - Documentation
- `dev-setup/DEV_SETUP.md` - Development setup guide
- `.env.development` - Configuration

See: `rust-scorer/comparison-tests/`, `dev-setup/DEV_SETUP.md`
