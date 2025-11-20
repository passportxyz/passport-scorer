# Rust Scorer Current Implementation Structure

## Current Implementation Status

### What's Already Implemented (COMPLETE):
1. **Main V2 API Endpoint**:
   - Route: `/v2/stamps/{scorer_id}/score/{address}` (GET)
   - Handler: `score_address_handler` in `src/api/handler.rs`
   - Full transaction management with commit/rollback
   - Includes all business logic: credential validation, LIFO dedup, scoring, event recording

2. **API Infrastructure**:
   - HTTP server setup with Axum in `src/api/server.rs`
   - Lambda support: Conditional logic in `main.rs` for Lambda vs local server
   - OpenTelemetry tracing configuration with ADOT sidecar support
   - Health check endpoint at `/health`
   - TowerHttp tracing layer for request instrumentation

3. **Authentication**:
   - API key validation with SHA-256 fast path in `src/auth/api_key.rs`
   - PBKDF2-SHA256 fallback for unmigrated keys
   - Analytics tracking for API usage and failed auth attempts
   - Permissions checking (read_scores permission)

4. **Database Operations** (in `src/db/`):
   - Read operations: load_ceramic_cache, get_latest_stamps_per_provider, load_scorer_config, load_community
   - Write operations: upsert_passport, delete_stamps, bulk_insert_stamps, upsert_score, insert_dedup_events, insert_score_update_event
   - All operations use correct i64 types (not i32) for IDs

5. **Core Scoring Logic**:
   - Credential validation from ceramic_cache
   - LIFO deduplication in `src/dedup/lifo.rs`
   - Score calculation in `src/scoring/calculation.rs`
   - Human points integration (all 15 action types)

6. **Response Handling**:
   - V2ScoreResponse model in `src/models/v2_api.rs`
   - Django database compatibility layer

### Architecture Pattern:
- Transactions started in handler, passed to helper functions
- Clean separation: business logic (scoring, dedup) → database compatibility layer
- All database operations require either &PgPool (read) or &mut Transaction (write)
- Strong instrumentation with tracing::instrument on all major functions

### What's NOT Implemented (EXPANSION NEEDED):
1. Internal endpoints without API key auth:
   - `/internal/score/{scorer_id}/{address}`
   - `/internal/embed/stamps/{address}`
   - `/internal/embed/score/{scorer_id}/{address}`
   - `/internal/embed/validate-api-key`

2. Ceramic cache endpoints with JWT auth:
   - `/ceramic-cache/stamps/bulk`
   - `/ceramic-cache/score/{address}`

3. JWT token validation module

4. Ceramic cache direct database operations (V1 only!)

### Key Technical Notes:
- All routes use Axum 0.8 syntax: `{param}` not `:param`
- Database connection pool: max 5 connections (RDS Proxy handles pooling)
- Transaction pattern: begin in handler, pass &mut tx to all db operations
- Error handling: ApiError enum with proper HTTP status mapping

## Complete Endpoint Inventory (15 Total)

### External/Public Endpoints (1 endpoint)
1. GET /v2/stamps/{scorer_id}/score/{address} - Main V2 scoring endpoint with API key auth, supports include_human_points query param

### Internal Embed Endpoints (3 endpoints)
2. GET /internal/embed/score/{scorer_id}/{address} - Get score with stamps
3. POST /internal/embed/stamps/{address} - Add stamps and rescore
4. GET /internal/embed/validate-api-key - Validate partner API key

### Ceramic Cache Endpoints (2 endpoints)
5. POST /ceramic-cache/stamps/bulk - Add stamps with JWT auth (HS256)
6. GET /ceramic-cache/score/{address} - Get score with JWT auth

### Internal API Endpoints (9 endpoints)
7. GET /internal/score/v2/{scorer_id}/{address} - Internal scoring
8. GET /internal/embed/weights - Weights retrieval (no auth required)
9. POST /internal/check-bans - Credential ban checking
10. POST /internal/check-revocations - Stamp revocation checking
11. GET /internal/allow-list/{list}/{address} - Allow list membership
12. GET /internal/customization/credential/{provider_id} - Credential definitions
13. GET /internal/stake/gtc/{address} - GTC stake retrieval
14. GET /internal/stake/legacy-gtc/{address}/{round_id} - Legacy GTC stake
15. GET /internal/cgrants/contributor_statistics - Contributor statistics

## Implementation Completeness Summary

**Fully Implemented (No Stubs)**: 6 endpoints
- All scoring (v2, embed, ceramic-cache)
- All embed operations

**Skeleton Complete, Database Complete**: 9 endpoints
- All handlers exist
- All domain logic implemented
- All database operations complete

### Details by Module

#### src/api/handlers/ - ALL COMPLETE
- internal.rs: 9 handler functions (100% complete, all call domain logic)
- external.rs: Scoring handler with API key auth
- mod.rs: Exports all handlers

#### src/domain/ - ALL COMPLETE
- scoring.rs: calculate_score_for_address() COMPLETE (441-552), build_scoring_result() COMPLETE (77-150)
- weights.rs: COMPLETE (with default weights fallback)
- stamps.rs: COMPLETE (add stamps, validate, etc.)
- allow_list.rs: COMPLETE (check membership)
- cgrants.rs: COMPLETE (contributor statistics)
- stakes.rs: COMPLETE (GTC staking queries)
- bans.rs: COMPLETE (credential ban checking)
- dedup.rs: COMPLETE (existing LIFO dedup)
- human_points.rs: COMPLETE (existing implementation)

#### src/db/ - COMPLETE FOR ALL ENDPOINTS
- read_ops.rs: All queries present
- write_ops.rs: All operations present

## Key Architectural Decisions

1. **Clean Separation**: HTTP concerns (handlers) separate from business logic (domain)
2. **Reusable Logic**: calculate_score_for_address can be called by both internal and external handlers
3. **Transaction Safety**: All operations maintain proper transaction semantics
4. **Error Types**: DomainError enum for business logic errors (Database, Validation, NotFound, Internal)
5. **Instrumentation**: All handlers and key domain functions have #[tracing::instrument] for observability

## Performance Targets

- Cold start <100ms (vs Python 2-5s)
- P50 <100ms, P95 <200ms, P99 <500ms
- Memory <256MB

## Performance Baseline Expectations

- Cold start: Python 2-5s vs Rust <100ms (20-50x)
- P50 latency: Python 100-200ms vs Rust <100ms
- P95 latency: Python 500-1000ms vs Rust <200ms
- P99 latency: Python 1500-2000ms vs Rust <500ms
- Memory: Python 512MB vs Rust <256MB target (2x efficiency)

See: `rust-scorer/src/api/server.rs`, `rust-scorer/src/api/handler.rs`, `rust-scorer/src/auth/api_key.rs`, `RUST_SCORER_EXPANSION_IMPLEMENTATION_GUIDE.md`
