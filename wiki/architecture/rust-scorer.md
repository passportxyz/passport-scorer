# Rust Scorer Implementation Status

All 15 endpoints fully implemented with complete domain logic and database queries. 13/13 comparison tests passing (Python/Rust parity verified).

## Implementation Summary

- **Main V2 endpoint**: `/v2/stamps/{scorer_id}/score/{address}` (GET)
- **Embed endpoints** (3): validate-api-key, add stamps, get score
- **Ceramic cache endpoints** (2): POST stamps/bulk, GET score
- **Internal API endpoints** (9): scoring, bans, stakes, cgrants, allow-list, weights, customization/credential

Location: `rust-scorer/src/`

## Architecture Pattern

Transactions started in handler, passed to helper functions:
1. Business logic (scoring, dedup, bans) - clean domain models
2. Database compatibility layer - Django table format conversion
3. Response formatting - 5 decimal place strings

All database ops require either `&PgPool` (read) or `&mut Transaction<Postgres>` (write).

## Key Features Implemented

- **API Key Auth**: SHA-256 fast path with PBKDF2 fallback (`src/auth/api_key.rs`)
- **LIFO Dedup**: 5-retry mechanism with bulk PostgreSQL UNNEST
- **Score Calculation**: Provider deduplication, rust_decimal for precision
- **Human Points**: All 15 action types with transaction consistency
- **Event Recording**: SCORE_UPDATE and dedup events
- **JWT Auth**: HS256 for ceramic cache endpoints
- **Internal Endpoints**: 9 utility endpoints (bans, stakes, cgrants, etc.)
- **Instrumentation**: tracing::instrument on all handlers and domain functions

## Database Operations

### Read Operations
- load_ceramic_cache: Fetch V1 stamps only, filter by type='V1'
- get_latest_stamps_per_provider: Latest per provider per address
- load_scorer_config: Check BinaryWeightedScorer then WeightedScorer tables
- load_community: Validate scorer_id exists (scorer_id is community_id)

### Write Operations
- upsert_passport: Create or return existing
- upsert_score: Save calculated score with evidence/stamp_scores/stamps JSON
- bulk_insert_stamps: Insert deduped stamps for passport
- delete_stamps: Remove stamps before rescoring
- insert_dedup_events: Record LIFO hash links
- insert_score_update_event: Record score update

### Transaction Pattern
```rust
let mut tx = pool.begin().await?;
// ... multiple db operations pass &mut tx
let score = upsert_score(&score_data, &mut tx).await?;
insert_score_update_event(&score, &mut tx).await?;
tx.commit().await?;
```

## Database Compatibility Requirements

- Evidence field format: `{"type": "ThresholdScoreCheck", "success": bool, "rawScore": "string", "threshold": "string"}`
- Stamps dict includes all stamps (deduped with score="0.00000")
- stamp_scores only valid stamps for calculation
- Binary score is Decimal(1) or Decimal(0)
- Connection pool: 5 max (RDS Proxy handles pooling)

## Key Type Details

- All IDs are i64 (BIGINT in PostgreSQL), not i32
- Weights are Decimal for exact precision matching Python
- Timestamps are ISO 8601 strings with timezone
- Provider field is empty string "" for no provider (not NULL)

## Performance Targets

- Cold start <100ms (vs Python 2-5s: 20-50x improvement)
- P50 <100ms, P95 <200ms, P99 <500ms
- Memory <256MB (vs Python 512MB: 2x efficiency)

## Files

- `src/api/server.rs`: Axum HTTP setup, OpenTelemetry config
- `src/api/handler.rs`: Main scoring handler with transaction management
- `src/api/handlers/{external,internal,embed,ceramic_cache}.rs`: Route handlers
- `src/auth/api_key.rs`: SHA-256 fast path auth with analytics
- `src/db/{read_ops,write_ops}.rs`: All database operations
- `src/domain/{scoring,dedup,bans,stakes,cgrants,weights,allow_list,human_points}.rs`: Business logic
- `src/models/{django,v2_api}.rs`: Database and response types
- `src/models/jwt.rs`: JWT validation for ceramic cache

## Routes

Axum 0.8 syntax uses `{param}` not `:param`:
```rust
.route("/v2/stamps/{scorer_id}/score/{address}", get(score_address_handler))
```

## Comparison Test Results

13/13 tests passing:
- Scoring accuracy
- Dedup logic
- Event recording
- Stamp handling
- Human points calculation
- Internal endpoints
- Auth flows
