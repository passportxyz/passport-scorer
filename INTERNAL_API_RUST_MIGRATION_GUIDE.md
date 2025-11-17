# Internal API Rust Migration Implementation Guide

## 🚀 PHASE 1 COMPLETION STATUS (Nov 2024)

### ✅ What's Done
- **Architecture refactoring complete** - Clean separation of concerns achieved
- **Domain layer created** - All business logic consolidated in `/src/domain/` as flat, simple files
- **API handlers split** - `/src/api/handlers/` with separate `external.rs` and `internal.rs`
- **Database queries organized** - `/src/db/queries/` modules created (stubs awaiting implementation)
- **Scoring orchestration implemented** - `calculate_score_for_address()` in `domain/scoring.rs` has full flow
- **All routes configured** - Server.rs updated with all internal endpoints
- **Human points models recovered** - Properly placed in `/src/models/human_points.rs`

### ⚠️ Key Deviations from Original Plan
1. **Flattened domain structure** - Instead of nested folders, domain uses flat files (e.g., `domain/scoring.rs` not `domain/scoring/mod.rs`)
2. **Preserved old code as comments** - Old `process_score_request` logic saved as comments in `embed.rs` for migration reference
3. **Query modules use SQLX macros** - Need `DATABASE_URL` or `cargo sqlx prepare` to compile
4. **Old handlers stubbed, not removed** - `embed.rs` and `ceramic_cache.rs` return errors but preserve implementation logic

### 🔄 Handoff to Phase 2 Team

#### Compilation Status
- **Current state**: Code doesn't compile due to SQLX query macros
- **To fix**: Either set `DATABASE_URL` env var OR run `cargo sqlx prepare` with a test database
- **Note**: All non-SQLX code is structurally correct

#### Key Files to Focus On
1. **`domain/scoring.rs:441-552`** - Main orchestration function `calculate_score_for_address()` - mostly complete, needs:
   - Zero score case handling (line 473)
   - Event recording implementation
   - Human points integration testing

2. **`api/handlers/internal.rs`** - All endpoint handlers stubbed, need implementation:
   - Each handler is a thin wrapper calling domain logic
   - Follow the pattern from `internal_score_handler` for others

3. **`db/queries/`** - Database query modules need actual implementation:
   - Currently have SQLX query! macros that need proper SQL
   - Follow existing patterns from `db/read_ops.rs` and `db/write_ops.rs`

#### Migration Reference
- **IMPORTANT**: Check comments in `api/embed.rs:129-187` for the original scoring flow
- This preserved logic shows exact order of operations from working code
- Use this as reference when implementing domain functions

#### Testing Approach
1. Start with `/internal/score/v2` endpoint - it uses the most complete code path
2. Use the preserved logic in embed.rs comments to verify correctness
3. Compare responses with Python implementation for exact match

#### Known Issues
- `cgrants` SQL queries in guide reference wrong columns (`from_address/to_address` don't exist, use `contributor`)
- Some function signatures may need adjustment as you implement
- Human points processing signature already fixed in domain layer

### 📋 Implementation Priority
Recommend implementing in this order for easiest path:
1. Fix SQLX compilation issues (set DATABASE_URL)
2. `/internal/score/v2` - Most code already done
3. `/internal/embed/weights` - Simple query
4. `/internal/allow-list` & `/internal/customization/credential` - Simple lookups
5. Ban/revocation endpoints - Moderate complexity
6. Stake endpoints - Moderate complexity
7. CGrants - Most complex

---

## Executive Summary

This guide documents the migration of 9 remaining Python internal API endpoints to Rust. These endpoints are currently experiencing performance issues due to `async_to_sync()` overhead and need to be migrated to maintain service reliability.

**Key Requirements:**
- This is a LIVE MIGRATION - match Python behavior exactly
- No changes to business logic, inputs, or outputs
- All endpoints run on internal ALB (no external authentication needed)
- Must maintain backward compatibility with existing consumers

## Current State Assessment

### Existing Rust Code Structure (Good Foundation ✅)
```
rust-scorer/src/
├── api/           # API handlers
├── auth/          # Authentication logic
├── db/            # Database operations
├── dedup/         # LIFO deduplication
├── human_points/  # Human points processing
├── models/        # Data models
└── scoring/       # Score calculation
```

**Current Issues:**
- API handlers mixed in single files (embed.rs, ceramic_cache.rs)
- No clear separation between internal vs external endpoints
- Database queries scattered across modules

## Proposed Architecture

### Recommended Module Organization

```rust
rust-scorer/src/
├── api/
│   ├── mod.rs
│   ├── server.rs         # Router configuration
│   ├── error.rs          # Shared error types
│   ├── handlers/         # THIN handlers - just auth + orchestration
│   │   ├── mod.rs
│   │   ├── external.rs   # Public endpoints (require API key)
│   │   └── internal.rs   # Internal endpoints (no auth)
│   └── responses/        # HTTP response formatting
│       ├── mod.rs
│       └── transformers.rs  # Convert domain types to HTTP responses
├── domain/               # NEW: SHARED business logic (no HTTP concerns!)
│   ├── mod.rs
│   ├── scoring.rs        # Score calculation logic (used by both internal/external)
│   ├── stamps.rs         # Stamp operations (add, get, validate)
│   ├── bans.rs           # Ban checking logic
│   ├── stakes.rs         # Staking queries and calculations
│   ├── cgrants.rs        # Grant contribution logic
│   ├── weights.rs        # Weight loading/management
│   └── allow_list.rs     # Allow list checking
├── db/
│   ├── queries/          # Raw database queries
│   │   ├── mod.rs
│   │   ├── ceramic_cache.rs
│   │   ├── bans.rs
│   │   ├── stakes.rs
│   │   ├── cgrants.rs
│   │   └── utils.rs
│   └── models/           # Database result types
│       ├── mod.rs
│       └── ...
└── models/
    ├── api/              # API request/response types
    │   ├── mod.rs
    │   ├── requests.rs   # Shared request types
    │   └── responses.rs  # Shared response types
    └── domain/           # Domain types (used in business logic)
        ├── mod.rs
        ├── score.rs
        ├── stake.rs
        └── grant.rs
```

### Key Architecture Principles

1. **Thin Handlers**: Handlers ONLY handle HTTP concerns
   - Extract parameters from request
   - Choose authentication method
   - Call domain logic
   - Transform domain result to HTTP response

2. **Shared Domain Logic**: Business logic lives in `domain/` modules
   - No HTTP types or concerns
   - Takes primitive types or domain types as input
   - Returns domain types (Result<T, DomainError>)
   - Used by BOTH internal and external handlers

3. **Clean Separation**:
   - `api/` = HTTP layer (handlers, routing, auth)
   - `domain/` = Business logic (calculations, validations, orchestration)
   - `db/` = Data layer (queries, transactions)

### Example: Scoring Endpoint (Shared Logic)

```rust
// ===== DOMAIN LAYER (domain/scoring.rs) =====
// Shared business logic - no HTTP concerns!
pub async fn calculate_score_for_address(
    address: &str,
    scorer_id: i64,
    pool: &PgPool,
) -> Result<ScoringResult, DomainError> {
    // All the scoring logic here
    // Used by BOTH internal and external endpoints
    let mut tx = pool.begin().await?;
    // ... scoring logic ...
    Ok(ScoringResult { /* domain type */ })
}

// ===== HANDLER LAYER (api/handlers/external.rs) =====
// Thin handler for external endpoint
pub async fn external_score_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    State(state): State<AppState>,
    headers: HeaderMap,
) -> ApiResult<Json<V2ScoreResponse>> {
    // 1. Auth check
    validate_api_key(&headers, &state.pool).await?;

    // 2. Call shared domain logic
    let result = domain::scoring::calculate_score_for_address(
        &address,
        scorer_id,
        &state.pool
    ).await?;

    // 3. Transform to HTTP response
    Ok(Json(result.into()))  // into() transforms domain type to API type
}

// ===== HANDLER LAYER (api/handlers/internal.rs) =====
// Thin handler for internal endpoint
pub async fn internal_score_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    State(state): State<AppState>,
) -> ApiResult<Json<V2ScoreResponse>> {
    // 1. No auth needed (internal ALB)

    // 2. Call SAME shared domain logic
    let result = domain::scoring::calculate_score_for_address(
        &address,
        scorer_id,
        &state.pool
    ).await?;

    // 3. Transform to HTTP response (same as external!)
    Ok(Json(result.into()))
}
```

### Example: Weights Endpoint (Shared Logic)

```rust
// ===== DOMAIN LAYER (domain/weights.rs) =====
pub async fn get_scorer_weights(
    scorer_id: Option<i32>,
    pool: &PgPool,
) -> Result<HashMap<String, f64>, DomainError> {
    // Shared weight loading logic
    if let Some(id) = scorer_id {
        load_community_weights(id, pool).await
    } else {
        Ok(get_default_weights())
    }
}

// ===== HANDLER LAYER (api/handlers/internal.rs) =====
pub async fn internal_weights_handler(
    Query(params): Query<HashMap<String, String>>,
    State(state): State<AppState>,
) -> ApiResult<Json<HashMap<String, f64>>> {
    // 1. Parse params
    let scorer_id = params.get("community_id")
        .and_then(|s| s.parse().ok());

    // 2. Call shared logic
    let weights = domain::weights::get_scorer_weights(scorer_id, &state.pool).await?;

    // 3. Return
    Ok(Json(weights))
}
```

## Endpoint Implementation Details

### 1. Simple Reuse Endpoints

#### GET /internal/score/v2/{scorer_id}/{address}
**Implementation:** Thin handler calling shared domain logic
```rust
// In api/handlers/internal.rs - THIN HANDLER
pub async fn internal_score_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    State(state): State<AppState>,
) -> ApiResult<Json<V2ScoreResponse>> {
    // Just orchestrate - no business logic here!
    let result = domain::scoring::calculate_score_for_address(
        &address,
        scorer_id,
        &state.pool
    ).await?;
    Ok(Json(result.into()))
}

// In domain/scoring.rs - SHARED BUSINESS LOGIC
pub async fn calculate_score_for_address(
    address: &str,
    scorer_id: i64,
    pool: &PgPool,
) -> Result<ScoringResult, DomainError> {
    // All the actual scoring logic
    // This same function is called by BOTH internal and external handlers
}
```

#### GET /internal/embed/weights
**SQL Query:**
```sql
-- Try BinaryWeightedScorer first
SELECT weights, threshold FROM scorer_weighted_binaryweightedscorer
WHERE scorer_ptr_id = $1

-- Fallback to WeightedScorer
SELECT weights, threshold FROM scorer_weighted_weightedscorer
WHERE scorer_ptr_id = $1
```

**Implementation:**
```rust
// In api/internal/utils.rs
pub async fn get_weights_handler(
    Query(params): Query<HashMap<String, String>>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<HashMap<String, f64>>> {
    let community_id = params.get("community_id")
        .and_then(|s| s.parse::<i32>().ok());

    // Reuse load_community() if community_id provided
    // Otherwise return default weights
}
```

### 2. Ban & Revocation Endpoints

**Architecture Note**: The ban checking logic is shared between multiple endpoints (ceramic cache operations check bans, scoring checks bans, etc.)

```rust
// In domain/bans.rs - SHARED LOGIC
pub async fn check_credentials_for_bans(
    address: &str,
    hashes: &[String],
    providers: &[String],
    pool: &PgPool,
) -> Result<Vec<BanCheckResult>, DomainError> {
    // Core ban checking logic
    // Used by multiple endpoints
    let bans = db::queries::bans::get_active_bans(address, hashes, pool).await?;

    // Apply ban logic
    providers.iter().map(|provider| {
        determine_ban_status(&bans, address, provider)
    }).collect()
}

// In api/handlers/internal.rs - THIN HANDLER
pub async fn check_bans_handler(
    State(state): State<AppState>,
    Json(credentials): Json<Vec<Credential>>,
) -> ApiResult<Json<Vec<CheckBanResult>>> {
    // 1. Extract data from request
    let address = extract_address_from_did(&credentials[0].credential_subject.id)?;
    let hashes = extract_hashes(&credentials);
    let providers = extract_providers(&credentials);

    // 2. Call shared domain logic
    let results = domain::bans::check_credentials_for_bans(
        &address,
        &hashes,
        &providers,
        &state.pool
    ).await?;

    // 3. Transform and return
    Ok(Json(results))
}
```

#### POST /internal/check-bans

**Request Type:**
```rust
#[derive(Deserialize)]
pub struct Credential {
    #[serde(rename = "credentialSubject")]
    pub credential_subject: CredentialSubject,
}

#[derive(Deserialize)]
pub struct CredentialSubject {
    pub id: String,      // DID string
    pub hash: Option<String>,
    pub provider: String,
}

#[derive(Serialize)]
pub struct CheckBanResult {
    pub hash: Option<String>,
    pub is_banned: bool,
    pub ban_type: Option<String>,  // "ADDRESS", "HASH", or "PROVIDER"
    pub end_time: Option<DateTime<Utc>>,
    pub reason: Option<String>,
}
```

**SQL Query:**
```sql
SELECT id, type, provider, hash, address, end_time, reason, ban_list_id
FROM ceramic_cache_ban
WHERE (address = $1 OR hash = ANY($2))
AND (end_time IS NULL OR end_time > NOW())
```

**Python Behavior to Match:**
- Returns empty array if no credentials provided
- All credentials must be for same address (extract from DID)
- Check ADDRESS bans, HASH bans, and PROVIDER bans
- Return ban details for each credential

#### POST /internal/check-revocations

**Request/Response Types:**
```rust
#[derive(Deserialize)]
pub struct RevocationCheckPayload {
    pub proof_values: Vec<String>,
}

#[derive(Serialize)]
pub struct RevocationCheckResponse {
    pub proof_value: String,
    pub is_revoked: bool,
}
```

**SQL Query:**
```sql
SELECT proof_value FROM ceramic_cache_revocation
WHERE proof_value = ANY($1)
```

### 3. Stake Endpoints

#### GET /internal/stake/gtc/{address}

**Response Type:**
```rust
#[derive(Serialize, sqlx::FromRow)]
pub struct StakeResponse {
    pub items: Vec<StakeSchema>,
}

#[derive(Serialize, sqlx::FromRow)]
pub struct StakeSchema {
    pub chain: String,
    pub staker: String,
    pub stakee: String,
    pub amount: Decimal,  // Use rust_decimal
    pub lock_time: DateTime<Utc>,
    pub unlock_time: DateTime<Utc>,
    pub last_updated_in_block: i64,
}
```

**SQL Query:**
```sql
SELECT id, chain, staker, stakee, current_amount as amount,
       lock_time, unlock_time, last_updated_in_block
FROM stake_stake
WHERE staker = $1 OR stakee = $1
```

**Python Behavior:** Returns empty array if no stakes found

#### GET /internal/stake/legacy-gtc/{address}/{round_id}

**Response Type:**
```rust
#[derive(Serialize)]
pub struct GtcEventsResponse {
    pub results: Vec<GtcStakeEvent>,
}

#[derive(Serialize, sqlx::FromRow)]
pub struct GtcStakeEvent {
    pub id: i64,
    pub address: String,
    pub amount: Decimal,
    pub staked: bool,
    pub staker: String,
    pub event_type: String,
    pub round_id: i32,
    pub tx_hash: String,
    pub block_number: i64,
}
```

**SQL Query:**
```sql
SELECT * FROM registry_gtcstakeevent
WHERE round_id = $1
AND (staker = $2 OR address = $2)
```

### 4. CGrants Endpoint (Most Complex)

#### GET /internal/cgrants/contributor_statistics?address={address}

**Response Type:**
```rust
#[derive(Serialize)]
pub struct ContributorStatistics {
    pub num_grants_contribute_to: i32,
    pub num_rounds_contribute_to: i32,
    pub total_contribution_amount: Decimal,
    pub num_gr14_contributions: i32,
}
```

**Required Queries:**

```sql
-- 1. Check if squelched (affects response)
SELECT EXISTS(
    SELECT 1 FROM cgrants_squelchedaccounts
    WHERE address = $1
)

-- 2. Count unique grants (cgrants)
SELECT COUNT(DISTINCT gci.grant_id)
FROM cgrants_grantcontributionindex gci
JOIN cgrants_contribution c ON gci.contribution_id = c.id
WHERE gci.contributor_address = $1
AND c.success = true

-- 3. Sum contribution amounts (cgrants)
SELECT COALESCE(SUM(gci.amount), 0) as total
FROM cgrants_grantcontributionindex gci
JOIN cgrants_contribution c ON gci.contribution_id = c.id
WHERE gci.contributor_address = $1
AND c.success = true

-- 4. Count unique protocol rounds
SELECT COUNT(DISTINCT round)
FROM cgrants_protocolcontributions
WHERE contributor = $1

-- 5. Sum protocol contribution amounts
SELECT COALESCE(SUM(amount), 0) as total_amount
FROM cgrants_protocolcontributions
WHERE contributor = $1

-- 6. GR14 specific count (hardcoded round)
-- Implementation note: GR14 round_id needs to be confirmed from Python code
```

**Python Behavior:**
- Returns all zeros if squelched
- Returns all zeros if no contributions
- Combines cgrants + protocol contributions

### 5. Utility Endpoints

#### GET /internal/allow-list/{list}/{address}

**Response Type:**
```rust
#[derive(Serialize)]
pub struct AllowListResponse {
    pub is_member: bool,
}
```

**SQL Query:**
```sql
SELECT EXISTS(
    SELECT 1 FROM account_addresslistmember alm
    JOIN account_addresslist al ON alm.list_id = al.id
    WHERE al.name = $1 AND alm.address = $2
)
```

#### GET /internal/customization/credential/{provider_id}

**Response Type:**
```rust
#[derive(Serialize)]
pub struct CredentialDefinitionResponse {
    pub ruleset: serde_json::Value,  // JSON object
}
```

**SQL Query:**
```sql
SELECT definition FROM account_customcredentialruleset
WHERE provider_id = $1
```

**Implementation Note:** Must URL-decode provider_id (replace %23 with #)


## Error Handling & Response Compatibility

### Match Python Error Responses

```rust
// Standard error response format
#[derive(Serialize)]
pub struct ErrorMessageResponse {
    pub detail: String,
}

// Return 200 with empty data for "not found" cases
// Return 400 for invalid input
// Return 500 for database errors
```

### Empty Data Handling (Match Python)

| Endpoint | Empty Response |
|----------|---------------|
| `/internal/stake/gtc/{address}` | `{"items": []}` |
| `/internal/stake/legacy-gtc/{address}/{round_id}` | `{"results": []}` |
| `/internal/cgrants/contributor_statistics` | All fields = 0 |
| `/internal/check-bans` | `[]` |
| `/internal/check-revocations` | `[]` with is_revoked=false for each |

## Testing Strategy

### Unit Tests
```rust
#[cfg(test)]
mod tests {
    // Test each query function with mock data
    // Test error handling
    // Test empty response handling
}
```

### Integration Tests
```rust
// In tests/internal_api_test.rs
#[tokio::test]
async fn test_stake_endpoint() {
    // Test against real test database
    // Verify response matches Python exactly
}
```

### Validation Checklist
- [ ] Response JSON structure matches Python exactly
- [ ] Field names match (snake_case)
- [ ] Null vs empty string handling matches
- [ ] Decimal precision matches (use rust_decimal)
- [ ] Datetime format matches (ISO 8601)
- [ ] Error responses match Python format

## Implementation Order

### Week 1: Foundation & Simple Endpoints
1. Set up new module structure
2. Implement `/internal/score/v2/{scorer_id}/{address}`
3. Implement `/internal/embed/weights`
4. Implement `/internal/allow-list/{list}/{address}`
5. Implement `/internal/customization/credential/{provider_id}`

### Week 2: Moderate Complexity
6. Implement `/internal/check-bans`
7. Implement `/internal/check-revocations`
8. Implement `/internal/stake/gtc/{address}`
9. Implement `/internal/stake/legacy-gtc/{address}/{round_id}`

### Week 3: Complex & Testing
10. Implement `/internal/cgrants/contributor_statistics`
11. Integration testing
12. Performance testing
13. Shadow traffic testing

## Deployment Notes

- Add routes to existing rust-scorer Lambda
- Use same PgPool connection pool
- Share existing tracing/observability setup
- No new environment variables needed (reuse existing DATABASE_URL)
- Test with shadow traffic before cutover

## Critical Migration Notes

⚠️ **DO NOT CHANGE**:
- Response field names or structure
- Business logic or calculations
- Error message text
- HTTP status codes for existing conditions

✅ **DO OPTIMIZE**:
- Use prepared statements
- Batch queries where possible
- Use connection pooling effectively

## Questions for Product Team

1. **CGrants GR14 Round ID**: Need to confirm the specific round_id for GR14 contributions
2. **Rate Limiting**: Should internal endpoints have any rate limiting?
3. **Monitoring**: What metrics should be tracked for these endpoints?
4. **Timeout Values**: What are acceptable response times for each endpoint?

## Success Criteria

- All endpoints return identical responses to Python implementation
- P95 latency < 200ms for all endpoints (currently 10-20s)
- Zero data inconsistencies during migration
- Clean, maintainable code structure
- Comprehensive test coverage

## Architecture Benefits Summary

### Why This Structure Works

1. **Shared Logic = Less Duplication**
   - Ban checking used by ceramic cache AND internal endpoints
   - Scoring logic used by v2 API AND internal endpoints
   - Weight loading used everywhere

2. **Thin Handlers = Easy Testing**
   - Handlers just orchestrate, easy to mock
   - Domain logic can be unit tested without HTTP
   - Database queries can be tested independently

3. **Clean Boundaries = Maintainability**
   ```
   Handler (api/) → Domain (domain/) → Database (db/)
   ```
   - Each layer has single responsibility
   - Easy to find where logic lives
   - Changes don't cascade across layers

4. **Future Flexibility**
   - Easy to add GraphQL? New handlers, same domain logic
   - Need gRPC? New handlers, same domain logic
   - Want to change auth? Only touch handlers

### Example: How Ban Logic Gets Reused

```
External ceramic cache endpoint → domain::bans::check_credentials_for_bans()
Internal check-bans endpoint   → domain::bans::check_credentials_for_bans()
Scoring logic (ban filtering)  → domain::bans::check_credentials_for_bans()
```

All three use the SAME ban checking logic, just called from different handlers with different auth methods.

---

**Document Version:** 1.1
**Last Updated:** November 2024
**Author:** Migration Team
**Status:** Ready for Implementation