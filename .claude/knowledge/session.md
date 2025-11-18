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

### [15:01] [api] AddStampsPayload scorer_id type flexibility
**Details**: The AddStampsPayload struct now accepts scorer_id as either a string or integer to handle clients that send it in either format. This is handled via a custom deserializer deserialize_scorer_id that accepts both i64 integers and strings that can be parsed to i64. This improves API compatibility with clients that serialize scorer_id differently.
**Files**: rust-scorer/src/models/v2_api.rs, rust-scorer/src/models/tests.rs
---

### [15:24] [api] Explicit scorer_id type handling in AddStampsPayload
**Details**: AddStampsPayload now explicitly handles scorer_id accepting both string and integer from JSON (matching Python's Pydantic behavior) but stores it as String type. The handler code explicitly calls parse_scorer_id() to convert to i64, making the type conversion visible and intentional rather than magic. This is more explicit than Python's implicit coercion while maintaining API compatibility.
**Files**: rust-scorer/src/models/v2_api.rs, rust-scorer/src/api/embed.rs, rust-scorer/src/models/tests.rs
---

### [18:22] [architecture] Internal API endpoint inventory and migration status
**Details**: Complete inventory of Python internal API endpoints and their migration status to Rust:

**Already Implemented in Rust (3 endpoints):**
1. GET /internal/embed/validate-api-key - validates partner API key
2. POST /internal/embed/stamps/{address} - adds stamps and rescores
3. GET /internal/embed/score/{scorer_id}/{address} - gets score with stamps

**NOT Yet Implemented in Rust (9 endpoints):**
1. GET /internal/score/v2/{scorer_id}/{address} - internal scoring without human points
2. GET /internal/embed/weights - retrieves scorer weights (NO AUTH REQUIRED!)
3. POST /internal/check-bans - checks credential bans
4. POST /internal/check-revocations - checks stamp revocations
5. GET /internal/stake/gtc/{address} - gets GTC stake amounts
6. GET /internal/stake/legacy-gtc/{address}/{round_id} - legacy GTC stake
7. GET /internal/cgrants/contributor_statistics - contributor stats
8. GET /internal/allow-list/{list}/{address} - checks allow list membership
9. GET /internal/customization/credential/{provider_id} - gets credential definition

**Authentication Notes:**
- Internal ALB endpoints don't require authentication (already inside VPC)
- Except /internal/embed/validate-api-key which validates the partner's API key
- Python uses CGRANTS_API_TOKEN from settings for internal_api_key auth
- Rust wouldn't need this since traffic is already authenticated at ALB level
**Files**: api/internal/api.py, rust-scorer/src/api/server.rs, rust-scorer/src/api/embed.rs
---

### [18:39] [database] Internal API SQL queries for Rust migration
**Details**: Extracted actual SQL queries from Django ORM for internal API endpoints:

**1. /internal/check-bans**
```sql
SELECT * FROM ceramic_cache_ban
WHERE (address = %(address)s OR hash = ANY(%(hashes)s))
AND (end_time IS NULL OR end_time > NOW())
```

**2. /internal/check-revocations**
```sql
SELECT proof_value FROM ceramic_cache_revocation
WHERE proof_value = ANY(%(proof_values)s)
```

**3. /internal/stake/gtc/{address}**
```sql
SELECT id, chain, lock_time, unlock_time, last_updated_in_block,
       staker, stakee, current_amount
FROM stake_stake
WHERE staker = %(address)s OR stakee = %(address)s
```

**4. /internal/stake/legacy-gtc/{address}/{round_id}**
```sql
SELECT * FROM registry_gtcstakeevent
WHERE round_id = %(round_id)s
AND (staker = %(address)s OR address = %(address)s)
```

**5. /internal/cgrants/contributor_statistics** (multiple queries):
- Check squelch: `SELECT * FROM cgrants_squelchedaccounts WHERE address = %(address)s`
- Count grants: `SELECT COUNT(DISTINCT grant_id) FROM cgrants_grantcontributionindex WHERE contributor_address = %(address)s AND contribution_id IN (SELECT id FROM cgrants_contribution WHERE success = true)`
- Sum amounts: `SELECT SUM(amount) FROM cgrants_grantcontributionindex WHERE contributor_address = %(address)s AND contribution_id IN (SELECT id FROM cgrants_contribution WHERE success = true)`
- Protocol rounds: `SELECT COUNT(DISTINCT round) FROM cgrants_protocolcontributions WHERE from_address = %(address)s OR to_address = %(address)s`
- Protocol sums: Separate SUMs for from_address and to_address

**6. /internal/allow-list/{list}/{address}**
```sql
SELECT EXISTS(
    SELECT 1 FROM account_addresslistmember alm
    JOIN account_addresslist al ON alm.list_id = al.id
    WHERE al.name = %(list_name)s AND alm.address = %(address)s
)
```

**7. /internal/customization/credential/{provider_id}**
```sql
SELECT definition FROM account_customcredentialruleset
WHERE provider_id = %(provider_id)s
```

**8. /internal/embed/weights**
No authentication, returns scorer weights from scorer_weighted_binaryweightedscorer or scorer_weighted_weightedscorer tables

**9. /internal/score/v2/{scorer_id}/{address}**
Reuses existing scoring logic without API key requirement
**Files**: api/internal/api.py, api/extract_sql_queries_v2.py
---

### [19:02] [architecture] Internal API Rust migration architecture decisions
**Details**: Key architectural decisions for internal API migration to Rust:

**Module Organization Pattern:**
- Separate `api/internal/` and `api/external/` directories for clear endpoint separation
- Domain-specific query modules in `db/queries/` (bans.rs, stakes.rs, cgrants.rs)
- Domain models separate from Django models in `db/models/`
- Internal API types in `models/internal/`

**Implementation Principles:**
1. LIVE MIGRATION - exact behavior match, no logic changes
2. Clean separation of concerns (handlers → queries → models)
3. Reuse existing connection pool and infrastructure
4. Group related endpoints in same module (e.g., all stake endpoints in stakes.rs)

**Key Design Decisions:**
- All internal endpoints in same Lambda as existing rust-scorer (simpler deployment)
- No authentication needed (internal ALB handles this)
- Match Python's empty data behavior exactly (return empty arrays, not 404s)
- Use prepared statements and recommend indexes for performance

**Testing Strategy:**
- Unit tests for each query function
- Integration tests against test database
- Shadow traffic before cutover
- Validation checklist for response compatibility

This architecture makes the codebase "pleasing to look at and work on" per user requirements, avoiding the "fucking trash" organization of the Python API.
**Files**: INTERNAL_API_RUST_MIGRATION_GUIDE.md
---

### [19:02] [database] Internal API database schema and performance notes
**Details**: Database schema details discovered for internal API migration:

**Table Names (actual Django tables):**
- `ceramic_cache_ban` - ban records with type, provider, hash, address, end_time
- `ceramic_cache_revocation` - revoked proof values
- `stake_stake` - GTC staking records with staker/stakee
- `registry_gtcstakeevent` - legacy staking events with staker/address fields (NOT stakee)
- `cgrants_grantcontributionindex` - grant contributions, joins to cgrants_contribution
- `cgrants_protocolcontributions` - protocol-level contributions
- `cgrants_squelchedaccounts` - addresses that should return zero stats
- `account_addresslist` / `account_addresslistmember` - allow list membership
- `account_customcredentialruleset` - custom credential definitions

**Performance Bottlenecks Identified:**
- Ban checks need compound index on (address, hash) with end_time filter
- Revocation checks are frequent and need index on proof_value
- CGrants queries are complex with multiple JOINs and aggregations
- Protocol contributions need compound index on (from_address, to_address)

**Field Type Gotchas:**
- GTCStakeEvent has 'staker' and 'address' fields, NOT 'stakee'
- GTCStakeEvent.staked is a boolean field
- All amounts should use Decimal type for precision
- Timestamps are timezone-aware (UTC)
- Empty provider names stored as empty string "", not NULL

**Query Optimization Notes:**
- CGrants endpoint makes 6 separate queries - consider CTE or parallel execution
- Use COALESCE for SUMs to handle NULL results as 0
- Protocol contributions need separate SUMs for from_address vs to_address
- Check squelched status first to potentially skip other queries
**Files**: api/extract_sql_queries_v2.py, INTERNAL_API_RUST_MIGRATION_GUIDE.md
---

### [19:11] [architecture] Clean architecture pattern for Rust API
**Details**: Key architectural pattern for clean Rust API design:

**Core Principle**: Handlers should be THIN - just pick auth, call shared logic, format response

**Three-Layer Architecture**:
1. **API Layer (api/)**: HTTP concerns only
   - Thin handlers that just orchestrate
   - Authentication decisions
   - Request parsing and response formatting
   - NO business logic

2. **Domain Layer (domain/)**: Shared business logic
   - Pure business logic, no HTTP types
   - Takes primitives or domain types as input
   - Returns domain types (Result<T, DomainError>)
   - Used by BOTH internal and external handlers
   - Examples: scoring.rs, bans.rs, stakes.rs, weights.rs

3. **Data Layer (db/)**: Database operations
   - Raw SQL queries in db/queries/
   - Database result types in db/models/
   - Transaction management

**Benefits**:
- Shared logic = no duplication (ban checking used by 3+ endpoints)
- Thin handlers = easy to test (can mock domain layer)
- Clean boundaries = maintainable (changes don't cascade)
- Future flexibility = easy to add GraphQL/gRPC (new handlers, same logic)

**Example Flow**:
```
External API → Handler (auth required) → domain::scoring::calculate() → db::queries
Internal API → Handler (no auth) → domain::scoring::calculate() → db::queries
```
Both use exact same business logic, just different auth at handler level.
**Files**: INTERNAL_API_RUST_MIGRATION_GUIDE.md
---

### [16:20] [workflow] Development environment setup structure
**Details**: Consolidated development setup into dev-setup/ folder with modular scripts:
- setup.sh: Main orchestrator script that detects environment (container vs systemd) and runs full setup
- install.sh: Basic dependency installer (Python, PostgreSQL, Rust, build tools)
- create_test_data.py: Django ORM-based test data creation
- start-postgres.sh: PostgreSQL restart helper for containers

The setup.sh automatically detects if running in container (no systemd) or regular system and adjusts PostgreSQL startup accordingly. Scripts are modular - setup.sh calls install.sh and create_test_data.py to avoid code duplication.

Database: passport_scorer_dev, User: passport_scorer, Password: devpassword123
Creates test communities (IDs 1-3), scorers, and API keys for testing.
**Files**: dev-setup/setup.sh, dev-setup/install.sh, dev-setup/create_test_data.py
---

### [16:20] [database] SQLX development database setup
**Details**: SQLX requires a PostgreSQL database at compile time for query validation. The setup process:
1. Creates PostgreSQL database passport_scorer_dev 
2. Runs Django migrations to create schema
3. Manually creates any missing tables that Django migrations didn't create (registry_*, ceramic_cache_ceramiccache, etc)
4. Installs sqlx-cli via: cargo install sqlx-cli --no-default-features --features postgres,rustls
5. Sets DATABASE_URL environment variable for SQLX compilation
6. Can generate offline data with 'cargo sqlx prepare' for CI/CD without database

Common issues:
- Missing tables: Django migrations may show as applied but tables don't exist - use migrate --run-syncdb
- Type mismatches: Some tables use BIGINT (i64) not INT (i32) for IDs
- Missing columns: May need to manually ALTER TABLE to add columns Django expects
**Files**: dev-setup/setup.sh, rust-scorer/Cargo.toml
---

### [16:21] [gotcha] Container vs system environment detection
**Details**: Development containers (Docker, dev containers) don't have systemd as PID 1, so PostgreSQL must be started differently:

Container detection logic:
- Checks for /.dockerenv or /run/.containerenv files
- Checks if systemd is running with pidof systemd
- If any indicate container, uses direct postgres command instead of systemctl

Container mode: sudo -u postgres /usr/bin/postgres -D /var/lib/postgresql/data &
System mode: sudo systemctl start postgresql

Also must create /var/run/postgresql directory for Unix socket in containers as it's not created automatically without systemd.
**Files**: dev-setup/setup.sh
---

