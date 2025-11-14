### [15:41] [architecture] Rust Scorer Current Implementation Structure
**Details**: ## Current Implementation Status

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

See: `rust-scorer/src/api/server.rs`, `rust-scorer/src/api/handler.rs`, `rust-scorer/src/auth/api_key.rs`, `RUST_SCORER_EXPANSION_IMPLEMENTATION_GUIDE.md`
**Files**: rust-scorer/src/api/server.rs, rust-scorer/src/api/handler.rs, rust-scorer/src/auth/api_key.rs, rust-scorer/src/db/read_ops.rs, rust-scorer/src/db/write_ops.rs, rust-scorer/src/main.rs
---

### [16:48] [phase2_implementation] Phase 2 Ceramic Cache Endpoints Complete
**Details**: Phase 2 of the Rust scorer expansion is complete with both ceramic-cache endpoints implemented:

**Implemented**:
1. JWT validation module (src/auth/jwt.rs) - Validates HS256 JWT tokens, extracts Ethereum address from DID claim format (did:pkh:eip155:1:0xADDRESS)
2. POST /ceramic-cache/stamps/bulk - Add stamps with JWT auth + header routing, reuses Phase 1 soft_delete and bulk_insert operations
3. GET /ceramic-cache/score/{address} - Get score with stamps and human points, validates JWT address matches path address
4. Header routing with X-Use-Rust-Scorer header - Returns 404 to fall back to Python if not set
5. Response types: InternalV2ScoreResponse, GetStampsWithInternalV2ScoreResponse, CacheStampPayload

**Key Design Decisions**:
- Reused all Phase 1 Layer 1 database operations (soft_delete_stamps_by_provider, bulk_insert_ceramic_cache_stamps, get_stamps_from_cache)
- JWT validation matches Python's ninja_jwt behavior exactly (HS256, DID claim extraction)
- Header routing for gradual rollout (X-Use-Rust-Scorer: true)
- Transaction safety maintained (ceramic cache ops in one tx, scoring in separate tx)
- source_app=1 (PASSPORT) for ceramic-cache vs source_app=2 (EMBED) for embed endpoints

**Testing**: 42 unit tests passing, zero compilation warnings, ready for integration testing with real JWT tokens and database.

**Performance**: Expected 30-120x faster than Python due to eliminating async_to_sync() overhead.
**Files**: rust-scorer/src/api/ceramic_cache.rs, rust-scorer/src/auth/jwt.rs, rust-scorer/src/models/v2_api.rs, rust-scorer/src/api/server.rs, RUST_SCORER_EXPANSION_IMPLEMENTATION_GUIDE.md
---

### [18:27] [gotcha] ALB listener rule priority ordering
**Details**: ALB listener rules are evaluated in order from LOWEST to HIGHEST priority number. More specific rules (e.g., with additional header conditions) must have LOWER priority numbers to be evaluated first.

For header-based routing to work correctly:
- Rust endpoints with X-Use-Rust-Scorer header: priorities 2090-2093 (evaluated first)
- Python endpoints without header requirement: priorities 2100-2103 (evaluated second)

If the priorities were reversed, the less specific Python rules would match first and the Rust rules would never be evaluated.
**Files**: infra/aws/v2/rust-scorer.ts, infra/aws/embed/index.ts
---

### [18:55] [gotcha] AWS target groups cannot span multiple load balancers
**Details**: AWS does not allow a single Lambda target group to be associated with more than one Application Load Balancer. When the same Lambda needs to serve requests from multiple ALBs (e.g., public and internal/private ALBs), you must create separate target groups for each ALB.

Solution:
- Create one target group per ALB
- Attach the same Lambda function to both target groups (with separate permissions)
- Use the appropriate target group ARN in listener rules for each ALB

For the Rust scorer:
- rustScorerTargetGroup (l-passport-v2-rust-scorer) - for public ALB endpoints (v2/stamps, ceramic-cache)
- rustScorerInternalTargetGroup (l-passport-v2-rust-scorer-int) - for internal ALB endpoints (embed)

Error message: "TargetGroupAssociationLimit: The following target groups cannot be associated with more than one load balancer"
**Files**: infra/aws/v2/rust-scorer.ts
---

