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

### [16:58] [architecture] Rust Scorer Internal API Implementation Status - Complete Architecture Overview
**Details**: The Rust scorer has been refactored with a complete new architecture separating concerns into API handlers, domain logic, and database operations. Here's the comprehensive status:

## Overall Architecture

The codebase has been reorganized into three clean layers:
1. **API Layer** (`src/api/handlers/`) - Thin HTTP handlers for routing and auth
2. **Domain Layer** (`src/domain/`) - Pure business logic with no HTTP concerns
3. **Database Layer** (`src/db/`) - Raw database queries and transactions

## Routes Implemented (All Configured in server.rs)

### Complete Implementation (Production-Ready):
1. **GET /v2/stamps/{scorer_id}/score/{address}** - External scoring (requires API key) - COMPLETE
2. **POST /internal/embed/stamps/{address}** - Add stamps and rescore - COMPLETE
3. **GET /internal/embed/score/{scorer_id}/{address}** - Get score with stamps - COMPLETE  
4. **GET /internal/embed/validate-api-key** - Validate partner API key - COMPLETE
5. **POST /ceramic-cache/stamps/bulk** - Ceramic cache add stamps with JWT - COMPLETE
6. **GET /ceramic-cache/score/{address}** - Ceramic cache get score - COMPLETE

### Stubbed Implementations (Awaiting Database Layer Implementation):
7. **GET /internal/score/v2/{scorer_id}/{address}** - Internal scoring endpoint
   - Handler: COMPLETE (calls domain::calculate_score_for_address)
   - Domain: COMPLETE (full orchestration at src/domain/scoring.rs:441-552)
   - Database: COMPLETE
   - Status: FUNCTIONAL

8. **GET /internal/embed/weights** - Get scorer weights
   - Handler: COMPLETE (src/api/handlers/internal.rs:63-86)
   - Domain: COMPLETE (src/domain/weights.rs with default weights)
   - Database: Uses existing load_scorer_config
   - Status: FUNCTIONAL

9. **GET /internal/allow-list/{list}/{address}** - Check allow list membership
   - Handler: COMPLETE (src/api/handlers/internal.rs:116-131)
   - Domain: STUBBED (returns false, TODO line 17)
   - Database: Not implemented
   - Status: NEEDS DB IMPLEMENTATION

10. **GET /internal/customization/credential/{provider_id}** - Get credential definition
    - Handler: COMPLETE (src/api/handlers/internal.rs:133-151)
    - Domain: STUBBED (returns empty JSON, TODO line 32)
    - Database: Not implemented
    - Status: NEEDS DB IMPLEMENTATION

### Phase 3 Endpoints (Database Queries Stubbed):
11. **POST /internal/check-bans** - Check for credential bans
    - Handler: STUBBED (src/api/handlers/internal.rs:88-102)
    - Domain: STUBBED (src/domain/bans.rs:17-34)
    - Database: Not implemented
    - Status: TODO IMPLEMENTATION

12. **POST /internal/check-revocations** - Check for credential revocations
    - Handler: STUBBED (src/api/handlers/internal.rs:104-114)
    - Domain: Not created
    - Database: Not implemented
    - Status: TODO IMPLEMENTATION

13. **GET /internal/stake/gtc/{address}** - Get GTC stakes
    - Handler: COMPLETE (src/api/handlers/internal.rs:154-169)
    - Domain: STUBBED (src/domain/stakes.rs:22-34, returns empty items)
    - Database: Not implemented
    - Status: NEEDS DB IMPLEMENTATION

14. **GET /internal/stake/legacy-gtc/{address}/{round_id}** - Get legacy GTC events
    - Handler: COMPLETE (src/api/handlers/internal.rs:171-186)
    - Domain: STUBBED (src/domain/stakes.rs:54-67, returns empty results)
    - Database: Not implemented
    - Status: NEEDS DB IMPLEMENTATION

15. **GET /internal/cgrants/contributor_statistics** - Get contributor stats
    - Handler: COMPLETE (src/api/handlers/internal.rs:188-206)
    - Domain: STUBBED (src/domain/cgrants.rs:16-35, returns zeros)
    - Database: Not implemented
    - Status: NEEDS DB IMPLEMENTATION

## Implementation Completeness Summary

**Fully Implemented (No Stubs)**: 6 endpoints
- All scoring (v2, embed, ceramic-cache)
- All embed operations

**Skeleton Complete, Database Pending**: 9 endpoints
- All handlers exist
- All domain types defined with TODO placeholders
- Database query logic needs implementation

**Details by Module**:

### src/api/handlers/ - ALL COMPLETE
- internal.rs: 9 handler functions (100% complete, all call domain logic)
- external.rs: Scoring handler with API key auth
- mod.rs: Exports all handlers

### src/domain/ - PARTIALLY COMPLETE
- scoring.rs: calculate_score_for_address() COMPLETE (441-552), build_scoring_result() COMPLETE (77-150)
- weights.rs: COMPLETE (with default weights fallback)
- stamps.rs: COMPLETE (add stamps, validate, etc.)
- allow_list.rs: STUBBED (check membership returns false)
- cgrants.rs: STUBBED (returns zeros)
- stakes.rs: STUBBED (returns empty arrays)
- bans.rs: STUBBED (returns empty results)
- dedup.rs: COMPLETE (existing LIFO dedup)
- human_points.rs: COMPLETE (existing implementation)

### src/db/ - COMPLETE FOR SCORING, NEEDS EXTENSIONS
- read_ops.rs: All scoring-related queries present
- write_ops.rs: All scoring-related operations present
- Need to add queries for:
  - allow_list (account_addresslistmember, account_addresslist)
  - cgrants (cgrants_grantcontributionindex, cgrants_protocolcontributions, cgrants_squelchedaccounts)
  - stakes (stake_stake, registry_gtcstakeevent)
  - bans (ceramic_cache_ban)
  - revocations (ceramic_cache_revocation)
  - custom credentials (account_customcredentialruleset)

## Key Architectural Decisions

1. **Clean Separation**: HTTP concerns (handlers) separate from business logic (domain)
2. **Reusable Logic**: calculate_score_for_address can be called by both internal and external handlers
3. **Transaction Safety**: All operations maintain proper transaction semantics
4. **Error Types**: DomainError enum for business logic errors (Database, Validation, NotFound, Internal)
5. **Instrumentation**: All handlers and key domain functions have #[tracing::instrument] for observability

## Known Issues/Limitations

1. **Zero Score Case**: Line 472-473 in scoring.rs marked TODO - currently returns error for addresses with no stamps
2. **Default Weights**: Hardcoded example weights in weights.rs need verification against Python defaults
3. **Phase 3 endpoints**: All database queries are not yet written (only stubs returning empty/zero values)

## File Locations Summary

Planning Documents:
- /workspace/project/RUST_SCORER_EXPANSION_IMPLEMENTATION_GUIDE.md - Phase 1 & 2 completion status
- /workspace/project/INTERNAL_API_RUST_MIGRATION_GUIDE.md - Architecture design for Phase 1 (now completed)

Source Code:
- Routes: /workspace/project/rust-scorer/src/api/server.rs (lines 178-242)
- External Handler: /workspace/project/rust-scorer/src/api/handlers/external.rs
- Internal Handlers: /workspace/project/rust-scorer/src/api/handlers/internal.rs (9 functions)
- Domain Logic: /workspace/project/rust-scorer/src/domain/ (10 modules)
- Database Ops: /workspace/project/rust-scorer/src/db/ (read_ops.rs, write_ops.rs)

## Next Steps for Completion

To complete the implementation, the database query functions need to be written for Phase 3 endpoints. The architecture and all HTTP handling is already in place - it's just a matter of implementing the SQL queries in the domain modules.
**Files**: /workspace/project/RUST_SCORER_EXPANSION_IMPLEMENTATION_GUIDE.md, /workspace/project/INTERNAL_API_RUST_MIGRATION_GUIDE.md, /workspace/project/rust-scorer/src/api/server.rs, /workspace/project/rust-scorer/src/api/handlers/internal.rs, /workspace/project/rust-scorer/src/domain/mod.rs, /workspace/project/rust-scorer/src/domain/scoring.rs, /workspace/project/rust-scorer/src/domain/weights.rs, /workspace/project/rust-scorer/src/domain/allows_list.rs, /workspace/project/rust-scorer/src/domain/cgrants.rs, /workspace/project/rust-scorer/src/domain/stakes.rs, /workspace/project/rust-scorer/src/domain/bans.rs
---

### [20:38] [api] CGrants Contributor Statistics Endpoint
**Details**: ## Endpoint Overview

**Endpoint Path**: `/internal/cgrants/contributor_statistics` (Internal API)
**HTTP Method**: GET
**Authentication**: `internal_api_key` (Bearer token in Authorization header)
**Route Name**: `cgrants_contributor_statistics`

## Request Parameters

- **address** (required, query parameter): Ethereum address to get contributor statistics for
  - Must be a valid Ethereum address (validated via `is_valid_address()`)
  - Converted to lowercase before processing
  - Returns 400 Bad Request if invalid
  - Returns 422 Unprocessable Entity if missing

## Response Structure

Returns a JSON object with 2 fields (always present, even for zero contributions):

```json
{
  "num_grants_contribute_to": <float>,
  "total_contribution_amount": <float>
}
```

All numeric values are returned as floats (not integers), rounded to 2 decimal places.

## Query Logic

The endpoint combines data from TWO separate data sources:

### 1. CGrants Contributions (_get_contributor_statistics_for_cgrants)

**Data Source**: GrantContributionIndex table
**Query Logic**:
- Filter by `contributor_address = address` AND `contribution.success = true` (FK join required)
- If no contributions found, return early with `{"num_grants_contribute_to": 0, "total_contribution_amount": 0}`
- Count distinct grant_id values (number of grants the user contributed to)
- Sum all amount fields (total contribution amount in USD)
- Returns dict with keys: `num_grants_contribute_to`, `total_contribution_amount`

**Key Points**:
- Only counts SUCCESSFUL contributions (contribution.success must be true)
- Sums the "amount" field from GrantContributionIndex (decimal with 18 places, max 64 digits)
- If sum is NULL (no rows after filtering), defaults to 0
- Uses `.distinct()` on grant_id values to ensure accurate count

### 2. Protocol Contributions (_get_contributor_statistics_for_protocol)

**Data Sources**: ProtocolContributions, SquelchedAccounts, RoundMapping tables
**Query Logic** (3-step process):

1. **Get squelched rounds**:
   - Query SquelchedAccounts where `address = address`
   - Extract list of `round_number` values

2. **Map round numbers to Ethereum addresses**:
   - Query RoundMapping where `round_number IN (squelched_round_ids)`
   - Extract list of `round_eth_address` values

3. **Get contributions excluding squelched rounds**:
   - Filter ProtocolContributions where:
     - `contributor = address` (case-sensitive ETH address comparison)
     - `amount >= 0.95` (minimum threshold to filter out depegged/low-value contributions)
   - Exclude rows where `round IN (squelched_round_ids)`
   - Count distinct `project` values (number of grants/projects)
   - Sum all `amount` fields (total contribution in USD)
   - Rounds result to 3 decimal places
   - Returns dict with keys: `num_grants_contribute_to`, `total_contribution_amount`

**Key Points**:
- Amount threshold is >= 0.95 (not 1.0) to account for depegged stablecoins
- Count is distinct by project, not by contribution
- Sum is rounded to 3 decimal places (not 2)
- Squelched/sybil addresses return 0 contributions for those rounds
- NULL sums default to 0

### 3. Combining Results

The final response combines both sources:
- For each key present in either source, add the values together
- Convert to float and round to 2 decimal places
- Result is a dict with keys: `num_grants_contribute_to`, `total_contribution_amount`

## Database Tables Involved

### GrantContributionIndex
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `profile_id` (FK to Profile)
  - `contribution_id` (FK to Contribution, nullable)
  - `grant_id` (FK to Grant)
  - `round_num` (IntegerField, nullable)
  - `amount` (DecimalField, 18 decimals, 64 max_digits)
  - `contributor_address` (EthAddressField, max_length=100, indexed, nullable)
- **Indexes**: contributor_address, contribution_id, profile_id
- **Purpose**: Fast lookup for contributor statistics

### Contribution
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `subscription_id` (FK to Subscription)
  - `success` (BooleanField, default=False)
  - `amount_per_period_usdt` (DecimalField, 18 decimals)
  - `data` (JSONField)
- **Join**: GrantContributionIndex.contribution_id → Contribution.id

### ProtocolContributions
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `ext_id` (CharField, max_length=66, unique, indexed)
  - `contributor` (EthAddressField, max_length=100, indexed) - the contributor's address
  - `round` (EthAddressField, max_length=100, indexed) - the round's Ethereum address
  - `project` (EthAddressField, max_length=100, indexed) - the project's address
  - `amount` (DecimalField, 18 decimals, 64 max_digits, indexed)
  - `data` (JSONField)
- **Indexes**: ext_id (unique), contributor, round, project, amount
- **Purpose**: Store Allo protocol contributions from indexer

### SquelchedAccounts
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `address` (EthAddressField, max_length=100, indexed)
  - `score_when_squelched` (DecimalField, 18 decimals)
  - `sybil_signal` (BooleanField)
  - `round_number` (CharField, max_length=100)
- **Index**: address
- **Purpose**: Track sybil/flagged addresses per round (GG18+)

### RoundMapping
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `round_number` (CharField, max_length=100)
  - `round_eth_address` (EthAddressField, max_length=100, indexed)
- **Unique Constraint**: (round_number, round_eth_address)
- **Purpose**: Map GG round numbers to Ethereum addresses

## Edge Cases and Special Handling

1. **No contributions**: Returns `{"num_grants_contribute_to": 0.0, "total_contribution_amount": 0.0}`
2. **Contributions below threshold** (< 0.95 USD): Ignored in protocol contributions, excluded from count
3. **Squelched addresses**: Contributions in those rounds are excluded from protocol stats
4. **Failed contributions**: Ignored in cgrants stats (contribution.success=false)
5. **NULL sums**: Converted to 0 (both queries handle this)
6. **Address case sensitivity**: Converted to lowercase before querying
7. **Invalid address**: Raises InvalidAddressException (400 Bad Request)
8. **Missing address**: Returns 422 Unprocessable Entity (Django Ninja validation)

## Response Schema

PydanticSchema `ContributorStatistics`:
```
- num_grants_contribute_to: int (Field, but returned as float)
- total_contribution_amount: int (Field, but returned as float)
```

Note: Schema declares int type but Python code converts to float before returning JsonResponse.

## Reference Implementation Files

- **Main handler**: `/workspace/project/api/cgrants/api.py::handle_get_contributor_statistics()`
- **CGrants logic**: `/workspace/project/api/cgrants/api.py::_get_contributor_statistics_for_cgrants()`
- **Protocol logic**: `/workspace/project/api/cgrants/api.py::_get_contributor_statistics_for_protocol()`
- **Route registration**: `/workspace/project/api/internal/api.py::cgrants_contributor_statistics()`
- **Models**: `/workspace/project/api/cgrants/models.py`
- **Tests**: `/workspace/project/api/cgrants/test/test_cgrants_combined_contributions_api.py`

## Test Coverage

Tests verify:
- Combined contributions from both sources
- Zero contributions for addresses with no history
- Invalid address handling (400 response)
- Invalid token handling (401 response)
- Missing address parameter (422 response)
- Contributions below threshold are excluded
- Only protocol contributions count correctly
- Depegged stablecoin handling (0.99897 rounded to 1.0)
- Squelched profiles excluded from protocol stats
- Squelched in one round but not another (mixed case)
**Files**: /workspace/project/api/cgrants/api.py, /workspace/project/api/cgrants/models.py, /workspace/project/api/internal/api.py, /workspace/project/api/cgrants/test/test_cgrants_combined_contributions_api.py
---

### [13:30] [architecture] Rust vs Python Endpoint Comparison and Test Infrastructure
**Details**: ## Complete Endpoint Mapping

**15 Total Endpoints Implemented (All Complete & Ready for Testing)**

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

## Implementation Status
- **Handlers**: All 15 handler functions complete in src/api/handlers/ and embed.rs/ceramic_cache.rs
- **Domain Logic**: All business logic implemented (scoring, dedup, human points, bans, stakes, etc.)
- **Database**: All database operations implemented for full response generation
- **Response Models**: All request/response types defined with exact Python compatibility

## Testing Infrastructure
- Rust: Unit tests (cargo test --lib), Integration tests (with DATABASE_URL)
- Python: Existing pytest-based tests
- Load Testing: K6 scripts with test data generation in load_tests/
- Database: Both use postgresql, migrations via Django ORM

## Key Architectural Patterns
- Both use transactional operations for data consistency
- API key auth: Python PBKDF2 (2.5s), Rust SHA-256 fast path (<1ms) with fallback
- JWT auth: HS256 with DID claim format extraction
- Response format: Identical JSON structures between Python and Rust
- Database: Same tables, types, schema - ensures exact parity

## Performance Baseline Expectations
- Cold start: Python 2-5s vs Rust <100ms (20-50x)
- P50 latency: Python 100-200ms vs Rust <100ms
- P95 latency: Python 500-1000ms vs Rust <200ms
- P99 latency: Python 1500-2000ms vs Rust <500ms
- Memory: Python 512MB vs Rust <256MB target (2x efficiency)

## Key Files for Comparison Testing
- Rust routes: rust-scorer/src/api/server.rs (lines 178-242)
- Python V2: api/v2/api/api_stamps.py
- Python Internal: api/internal/api.py
- Load tests: load_tests/ with K6 scripts
- Documentation: RUST_PYTHON_ENDPOINTS_COMPARISON.md, RUST_DEVELOPMENT_QUICKSTART.md (newly created)
**Files**: rust-scorer/src/api/server.rs, rust-scorer/src/api/handlers/external.rs, rust-scorer/src/api/handlers/internal.rs, rust-scorer/src/api/embed.rs, rust-scorer/src/api/ceramic_cache.rs, api/v2/api/api_stamps.py, api/internal/api.py, api/embed/api.py, api/embed/lambda_fn.py, load_tests/
---

### [14:53] [testing] Comparison test infrastructure for Python/Rust migration
**Details**: Created comparison-tests infrastructure in rust-scorer/comparison-tests/ that:
- Auto-loads .env.development using dotenvy (standard format, no export/shell vars)
- Starts both Python (8002) and Rust (3000) servers
- Compares JSON responses with sorted keys
- First test: /internal/embed/weights endpoint passing

Key fixes made:
- Scorer type must be 'WEIGHTED_BINARY' not 'BinaryWeightedScorer'
- CERAMIC_CACHE_SCORER_ID required in env
- DATABASE_URL needs ?sslmode=disable for local PostgreSQL
- Redis/Valkey required for Django caching

Remaining work: Add scoring endpoint tests with valid credentials, API key auth, POST endpoints
**Files**: rust-scorer/comparison-tests/src/main.rs, rust-scorer/comparison-tests/HANDOFF.md, dev-setup/DEV_SETUP.md, .env.development
---

### [12:44] [gotchas] DIDKit Rust EIP-712 signing requires correct TypedData structure
**Details**: When signing credentials with EthereumEip712Signature2021 using DIDKit's Rust SSI library, the eip712_domain field in LinkedDataProofOptions must be a properly structured TypedData object from ssi::ldp::eip712, not a raw JSON value. The library expects the domain, types, and primaryType to be in the correct format that matches the TypedData struct definition.
**Files**: rust-scorer/comparison-tests/src/gen_credentials.rs
---

### [13:01] [gotchas] EIP-712 credential @context structure for production
**Details**: When creating Passport credentials with EthereumEip712Signature2021 signatures, the nested JSON-LD context object must be placed in credentialSubject.@context, NOT in the top-level credential @context array. 

Top-level @context should only contain URI strings:
@context: ["https://www.w3.org/2018/credentials/v1", "https://w3id.org/vc/status-list/2021/v1"]

The nested definitions go in credentialSubject:
credentialSubject: {
  "@context": {
    "provider": "https://schema.org/Text",
    "nullifiers": {
      "@type": "https://schema.org/Text",
      "@container": "@list"
    }
  }
}

This structure allows DIDKit's EIP-712 TypedData generator to properly parse the credential without "Expected string" errors.
**Files**: rust-scorer/comparison-tests/src/gen_credentials.rs
---

