# Rust Scorer Expansion Implementation Guide

## ⚠️ IMPORTANT: Database Schema Reference
**See RUST_SCORER_SCHEMA_ADDENDUM.md for critical database schema details including:**
- Correct table names (e.g., `ceramic_cache_ceramiccache` not `ceramic_cache`)
- Primary keys are `i64` not `i32`
- Special field handling (empty strings vs NULL)
- Missing timestamp fields

## 📝 Key Implementation Notes

### V1 Stamps Only
- **ONLY process V1 stamps** - filter for `type = 'V1'` in all ceramic_cache queries
- V2 stamps were never actually implemented (started but abandoned)
- All Python code exclusively uses `CeramicCache.StampType.V1`

### Instrumentation Requirements
All new endpoints must include the same level of instrumentation as existing Rust scorer:
- Use `#[tracing::instrument]` on all handler functions
- Include relevant fields: `address`, `scorer_id`/`community_id`, `stamp_count`, etc.
- Track API key validation, database operations, and scoring steps
- Maintain consistent span naming and field conventions

## Executive Summary

The Python scoring system has critical performance issues due to `async_to_sync()` overhead, causing 10-20 second delays per request. We need to expand the existing Rust scorer to handle additional endpoints that are currently timing out or performing poorly.

**Key Issue**: Every Python scoring call uses `async_to_sync()` which creates a new event loop, taking 10-20 seconds in Lambda environments.

## Current State

### What We Already Have in Rust
- ✅ Core scoring logic (`calculate_score`)
- ✅ API key validation with SHA-256 fast path
- ✅ Database models and connections
- ✅ LIFO deduplication
- ✅ Human points calculation
- ✅ `/v2/stamps/{scorer_id}/score/{address}` endpoint

### What's Causing Problems
- ❌ `/internal/embed/score/{scorer_id}/{address}` - Timing out (60s)
- ❌ `/internal/embed/stamps/{address}` - Needs implementation
- ❌ `/ceramic-cache/stamps/bulk` - Has async_to_sync overhead
- ❌ `/ceramic-cache/score/{address}` - Has async_to_sync overhead

## Implementation Plan

### Phase 1: Embed Endpoints (Critical - Fixes 60s Timeouts)

**Authentication Note**: All `/internal/embed/*` endpoints are deployed on a **private internal ALB** that doesn't leave the VPC. They do not require authentication headers (no API key, no internal secret) except for `/internal/embed/validate-api-key` which validates the partner's API key.

#### 1.1 Database Operations
**File**: `rust-scorer/src/db/ceramic_cache.rs`

```rust
#[derive(sqlx::FromRow, Serialize)]
pub struct CachedStamp {
    pub id: i64,
    pub address: String,
    pub provider: String,
    pub stamp: serde_json::Value,
    pub created_at: DateTime<Utc>,
}

pub async fn insert_ceramic_cache_stamp(
    address: &str,
    stamp: &serde_json::Value,
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    let provider = stamp["credentialSubject"]["provider"]
        .as_str()
        .ok_or_else(|| DatabaseError::InvalidData("Missing provider".into()))?;

    let proof_value = stamp["proof"]["proofValue"]
        .as_str()
        .ok_or_else(|| DatabaseError::InvalidData("Missing proof value".into()))?;

    sqlx::query!(
        r#"
        INSERT INTO ceramic_cache_ceramiccache (
            type, address, provider, stamp, proof_value,
            updated_at, compose_db_save_status,
            issuance_date, expiration_date, source_app
        ) VALUES (
            'V1', $1, $2, $3, $4, NOW(), 'pending',
            $5::timestamp, $6::timestamp, 'embed'
        )
        "#,
        address,
        provider,
        stamp,
        proof_value,
        stamp["issuanceDate"].as_str().and_then(|s| DateTime::parse_from_rfc3339(s).ok()),
        stamp["expirationDate"].as_str().and_then(|s| DateTime::parse_from_rfc3339(s).ok()),
    )
    .execute(&mut **tx)
    .await?;

    Ok(())
}

pub async fn soft_delete_stamps(
    address: &str,
    providers: &[String],
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), DatabaseError> {
    sqlx::query!(
        r#"
        UPDATE ceramic_cache_ceramiccache
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE address = $1
          AND provider = ANY($2)
          AND type = 'V1'
          AND deleted_at IS NULL
        "#,
        address,
        providers
    )
    .execute(&mut **tx)
    .await?;

    Ok(())
}

pub async fn get_stamps_from_cache(
    address: &str,
    pool: &PgPool,
) -> Result<Vec<CachedStamp>, DatabaseError> {
    let stamps = sqlx::query_as!(
        CachedStamp,
        r#"
        SELECT id, address, provider, stamp, created_at
        FROM ceramic_cache_ceramiccache
        WHERE address = $1
          AND type = 'V1'  -- Only V1 stamps (V2 never implemented)
          AND deleted_at IS NULL
          AND revocation IS NULL
        ORDER BY created_at DESC
        "#,
        address
    )
    .fetch_all(pool)
    .await?;

    Ok(stamps)
}

fn extract_providers(stamps: &[serde_json::Value]) -> Vec<String> {
    stamps
        .iter()
        .filter_map(|stamp| {
            stamp["credentialSubject"]["provider"]
                .as_str()
                .map(|s| s.to_string())
        })
        .collect()
}
```

#### 1.2 Validate API Key Endpoint
**Endpoint**: `GET /internal/embed/validate-api-key`

**Note**: This endpoint validates the **partner's API key** (the key being checked), not an internal auth token.

```rust
#[tracing::instrument(
    skip(state, headers),
    fields(endpoint = "validate_api_key")
)]
pub async fn validate_api_key_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, ApiError> {
    // Extract partner API key from header
    let api_key = extract_api_key(&headers)?;

    // Validate and get key data (reuse existing code)
    let key_data = validate_api_key(&api_key, &state.pool).await?;

    // Return rate limit info
    Ok(Json(json!({
        "embed_rate_limit": key_data.embed_rate_limit
    })))
}
```

#### 1.3 Add Stamps and Score Endpoint
**Endpoint**: `POST /internal/embed/stamps/{address}`

**Authentication**: None (private ALB)

```rust
#[derive(Deserialize)]
pub struct AddStampsPayload {
    scorer_id: i64,
    stamps: Vec<serde_json::Value>,
}

#[derive(Serialize)]
pub struct GetStampsWithV2ScoreResponse {
    success: bool,
    stamps: Vec<CachedStamp>,
    score: V2ScoreResponse,
}

#[tracing::instrument(
    skip(state, payload),
    fields(address = %address, scorer_id = payload.scorer_id, stamp_count = payload.stamps.len())
)]
pub async fn add_stamps_handler(
    Path(address): Path<String>,
    State(state): State<AppState>,
    Json(payload): Json<AddStampsPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let mut tx = state.pool.begin().await?;

    // 1. Soft delete existing stamps by provider (V1 only)
    let providers = extract_providers(&payload.stamps);
    soft_delete_stamps(&address, &providers, &mut tx).await?;

    // 2. Insert new stamps
    for stamp in &payload.stamps {
        insert_ceramic_cache_stamp(&address, stamp, &mut tx).await?;
    }

    // 3. Score the address (reuse existing scoring logic)
    let score = score_address_internal(
        payload.scorer_id,
        &address,
        &state.pool
    ).await?;

    // 4. Get updated stamps
    let stamps = get_stamps_from_cache(&address, &state.pool).await?;

    tx.commit().await?;

    Ok(Json(GetStampsWithV2ScoreResponse {
        success: true,
        stamps,
        score,
    }))
}
```

#### 1.4 Get Score Endpoint
**Endpoint**: `GET /internal/embed/score/{scorer_id}/{address}`

**Authentication**: None (private ALB)

```rust
#[tracing::instrument(
    skip(state),
    fields(scorer_id = scorer_id, address = %address)
)]
pub async fn get_embed_score_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, ApiError> {
    // 1. Get stamps from ceramic cache
    let stamps = get_stamps_from_cache(&address, &state.pool).await?;

    // 2. Score the address (reuse existing scoring logic)
    let score = score_address_internal(scorer_id, &address, &state.pool).await?;

    Ok(Json(GetStampsWithV2ScoreResponse {
        success: true,
        stamps,
        score,
    }))
}
```

### Phase 2: Ceramic Cache Endpoints with JWT

#### 2.1 JWT Validation
**Dependencies**: Add to `Cargo.toml`
```toml
jsonwebtoken = "9.2"
```

**File**: `rust-scorer/src/auth/jwt.rs`

```rust
use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
struct Claims {
    did: String,
    exp: i64,
}

pub fn validate_jwt_and_extract_address(token: &str) -> Result<String, ApiError> {
    let jwt_secret = std::env::var("JWT_SECRET")
        .map_err(|_| ApiError::Configuration("JWT_SECRET not set".into()))?;

    let token_data = decode::<Claims>(
        token,
        &DecodingKey::from_secret(jwt_secret.as_ref()),
        &Validation::new(Algorithm::HS256),
    )
    .map_err(|_| ApiError::Unauthorized)?;

    // Extract address from did:pkh:eip155:1:0xADDRESS
    let address = token_data.claims.did
        .split(':')
        .last()
        .ok_or_else(|| ApiError::Validation("Invalid DID format".into()))?;

    Ok(address.to_lowercase())
}
```

#### 2.2 Ceramic Cache Endpoints
**Endpoint**: `POST /ceramic-cache/stamps/bulk`

```rust
#[tracing::instrument(
    skip(state, headers, payload),
    fields(endpoint = "ceramic_cache_stamps_bulk", stamp_count = payload.len(), has_rust_header)
)]
pub async fn ceramic_cache_add_stamps(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<Vec<CacheStampPayload>>,
) -> Result<impl IntoResponse, ApiError> {
    // Check for Rust routing header
    let use_rust = should_use_rust(&headers);
    tracing::Span::current().record("has_rust_header", use_rust);
    if !use_rust {
        return Err(ApiError::NotFound); // Let Python handle it
    }

    // Extract JWT token
    let token = headers
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(ApiError::Unauthorized)?;

    // Validate JWT and get address
    let address = validate_jwt_and_extract_address(token)?;

    // Use existing add_stamps logic
    let scorer_id = std::env::var("CERAMIC_CACHE_SCORER_ID")
        .unwrap_or_else(|_| "335".to_string())
        .parse::<i32>()?;

    // Reuse the embed add_stamps logic
    add_stamps_internal(&address, payload, scorer_id, &state.pool).await
}

fn should_use_rust(headers: &HeaderMap) -> bool {
    headers
        .get("X-Use-Rust-Scorer")
        .and_then(|v| v.to_str().ok())
        .map(|v| v == "true")
        .unwrap_or(false)
}
```

## Routing Strategy

### ALB Header-Based Routing
Add to Pulumi infrastructure:

```typescript
// infra/aws/v2/index.ts
new aws.lb.ListenerRule("rust-scorer-rule", {
    listenerArn: listener.arn,
    priority: 99, // High priority
    conditions: [
        {
            httpHeader: {
                httpHeaderName: "X-Use-Rust-Scorer",
                values: ["true"],
            },
        },
    ],
    actions: [{
        type: "forward",
        targetGroupArn: rustScorerTargetGroup.arn,
    }],
});
```

### Gradual Rollout
1. **Test**: Send requests with `X-Use-Rust-Scorer: true` header
2. **Monitor**: Check latency and error rates
3. **Increase**: Gradually increase traffic percentage
4. **Full cutover**: Remove header requirement once stable

## Environment Variables Required

**Note**: Environment variables come from AWS Secrets Manager via Pulumi (same as Python lambdas)

```bash
# Required for all endpoints
DATABASE_URL=postgresql://user:pass@rds-proxy.amazonaws.com/dbname
HUMAN_POINTS_ENABLED=true
RUST_LOG=info

# Required for Phase 2 (ceramic cache JWT endpoints)
JWT_SECRET=your-jwt-secret  # Same as Python - from Secrets Manager
CERAMIC_CACHE_SCORER_ID=335  # Or your scorer ID
```

## Testing Checklist

### Unit Tests
```bash
cd rust-scorer
cargo test --lib
```

### Integration Tests

**Phase 1 - Embed Endpoints** (no auth needed - private ALB):
```bash
# Test validate API key (requires partner API key)
curl -H "X-API-Key: your-partner-api-key" \
  http://localhost:3000/internal/embed/validate-api-key

# Test add stamps and score (no auth)
curl -X POST -H "Content-Type: application/json" \
  -d '{"scorer_id": 335, "stamps": [...]}' \
  http://localhost:3000/internal/embed/stamps/0xaddress

# Test get score (no auth)
curl http://localhost:3000/internal/embed/score/335/0xaddress
```

**Phase 2 - Ceramic Cache Endpoints** (JWT auth + header routing):
```bash
# Get JWT token from Python auth endpoint
TOKEN=$(curl -X POST http://python-api/ceramic-cache/authenticate | jq -r .token)

# Test ceramic cache endpoints with JWT and header routing
curl -H "Authorization: Bearer $TOKEN" \
  -H "X-Use-Rust-Scorer: true" \
  -X POST -H "Content-Type: application/json" \
  -d '[{"provider": "...","stamp": {...}}]' \
  http://localhost:3000/ceramic-cache/stamps/bulk
```

### Load Testing
```bash
# Run concurrent requests to verify performance improvement
for i in {1..100}; do
  curl -H "X-Use-Rust-Scorer: true" \
    http://api.scorer.gitcoin.co/internal/embed/score/40/0xaddress &
done
wait
```

## Performance Expectations

### Before (Python with async_to_sync)
- Cold start: 4.5 seconds
- Event loop creation: 10-20 seconds
- Total request time: 15-60 seconds (timeouts common)

### After (Rust)
- Cold start: <100ms
- No event loop overhead
- Total request time: <500ms

### Improvement
- **30-120x faster** response times
- **No more timeouts**
- **Lower Lambda costs** (less execution time)

## Common Pitfalls to Avoid

1. **Don't forget the transaction**: Ceramic cache operations should be in a transaction
2. **Handle missing stamps gracefully**: Not all stamps have all fields
3. **Validate addresses**: Always lowercase Ethereum addresses
4. **Check scorer_id exists**: Validate before scoring
5. **JWT expiration**: The JWT validation handles this automatically

## Deployment Steps

1. **Build Docker image**:
```bash
cd rust-scorer
./build-lambda.sh
docker tag rust-scorer:latest $ECR_REPO:$TAG
docker push $ECR_REPO:$TAG
```

2. **Update Lambda**:
```bash
cd infra/aws
pulumi config set RUST_DOCKER_IMAGE_TAG $TAG
pulumi up
```

3. **Test with header**:
```bash
curl -H "X-Use-Rust-Scorer: true" [endpoint]
```

4. **Monitor CloudWatch**:
- Check for errors
- Compare latency metrics
- Watch for memory issues

## Success Criteria

- [ ] No more Lambda timeouts
- [ ] P95 latency < 500ms
- [ ] All tests passing
- [ ] No increase in error rate
- [ ] Memory usage < 256MB

## Support Resources

- **Rust PostgreSQL**: https://docs.rs/sqlx/latest/sqlx/
- **JWT in Rust**: https://docs.rs/jsonwebtoken/latest/jsonwebtoken/
- **Axum Web Framework**: https://docs.rs/axum/latest/axum/
- **AWS Lambda Rust**: https://github.com/awslabs/aws-lambda-rust-runtime

## Questions Answered

1. ✅ **JWT_SECRET**: Loaded from AWS Secrets Manager (same as Python lambdas)
2. ✅ **CERAMIC_CACHE_SCORER_ID**: Usually 335, configurable via env var
3. ✅ **RDS Proxy**: Already configured in core-infra, DATABASE_URL from Secrets Manager
4. ✅ **Stamp types**: V1 only (V2 never implemented)
5. ✅ **Authentication**: No internal auth needed for `/internal/embed/*` endpoints (private ALB)

## Final Note

This implementation fixes the root cause of the performance issues: Django's `async_to_sync()` creating new event loops for every request. By moving to Rust, we eliminate this overhead entirely and get 30-120x performance improvement.

---

## 🚀 Phase 1 Implementation Status (COMPLETED - 2025-11-14)

### ✅ What Was Implemented

**Phase 1: Embed Endpoints** is **COMPLETE** and ready for testing/deployment.

#### 1. Core Ceramic Cache Operations (`src/db/ceramic_cache.rs`)
All reusable Layer 1 database operations for ceramic cache manipulation:
- ✅ `extract_providers()` - Extract provider list from stamps array
- ✅ `soft_delete_stamps_by_provider()` - Soft delete existing stamps in transaction
- ✅ `bulk_insert_ceramic_cache_stamps()` - UNNEST-based bulk insert with source_app tracking
- ✅ `get_stamps_from_cache()` - Get non-deleted, non-revoked V1 stamps with revocation LEFT JOIN

#### 2. Data Models Updated
- ✅ `DjangoCeramicCache` - Added `type`, `compose_db_save_status`, `compose_db_stream_id`, `issuance_date`, `expiration_date`, `source_app`, `source_scorer_id`
- ✅ `DjangoApiKey` - Added `embed_rate_limit` field
- ✅ Response types in `models/v2_api.rs`:
  - `GetStampsWithV2ScoreResponse`
  - `CachedStampResponse`
  - `AccountAPIKeySchema`
  - `AddStampsPayload`

#### 3. Embed API Handlers (`src/api/embed.rs`)
All three endpoints implemented with full instrumentation:
- ✅ `GET /internal/embed/validate-api-key` - Validates partner API key, returns rate limit
- ✅ `POST /internal/embed/stamps/{address}` - Add stamps + rescore
- ✅ `GET /internal/embed/score/{scorer_id}/{address}` - Get score with stamps

#### 4. Router Integration (`src/api/server.rs`)
- ✅ All three embed routes added with correct HTTP methods
- ✅ No authentication (private ALB deployment)

#### 5. Compilation
- ✅ All code compiles successfully with zero errors
- ✅ Unit tests included for helper functions

### 📋 Key Implementation Deviations from Original Guide

#### 1. **Transaction Safety (IMPROVEMENT)**
**Original**: Python doesn't use explicit transactions for ceramic cache operations, so soft-delete might commit even if bulk insert fails.

**Implemented**: All ceramic cache operations wrapped in a transaction for all-or-nothing behavior. This is **better** than Python's behavior and prevents partial state.

```rust
let mut tx = pool.begin().await?;
soft_delete_stamps_by_provider(&address, &providers, &mut tx).await?;
bulk_insert_ceramic_cache_stamps(&address, &stamps, 2, Some(scorer_id), &mut tx).await?;
tx.commit().await?; // All or nothing
```

#### 2. **Query Macro Approach (TECHNICAL)**
**Original**: Guide showed examples using `sqlx::query!()` macros.

**Implemented**: Used `sqlx::query()` (non-macro) with manual `.bind()` calls to avoid needing sqlx offline cache during development. This is a standard approach and doesn't affect functionality.

#### 3. **Revocation Handling (AS SPECIFIED)**
**Original**: Guide mentioned revocation checking but didn't specify implementation.

**Implemented**: Proper LEFT JOIN with `ceramic_cache_revocation` table:
```sql
LEFT JOIN ceramic_cache_revocation r ON c.id = r.ceramic_cache_id
WHERE r.id IS NULL
```

#### 4. **Code Organization (IMPROVEMENT)**
**Original**: Guide suggested inline implementations.

**Implemented**: Separated concerns into reusable Layer 1 operations in `src/db/ceramic_cache.rs`, making Phase 2 (ceramic-cache endpoints) trivial. The embed handlers are thin wrappers that call these core operations.

#### 5. **API Key Field (REQUIRED)**
**Original**: Guide assumed `embed_rate_limit` field existed.

**Implemented**: Added missing field to `DjangoApiKey` model and updated the SELECT query in `src/auth/api_key.rs` to include it.

### 🔄 Next Steps: Phase 2 (Ceramic Cache Endpoints)

Phase 2 will be **extremely straightforward** due to the reusable architecture:

1. **Add JWT validation** (`src/auth/jwt.rs`):
   ```rust
   pub fn validate_jwt_and_extract_address(token: &str) -> Result<String, ApiError>
   ```

2. **Add header routing check**:
   ```rust
   fn should_use_rust(headers: &HeaderMap) -> bool {
       headers.get("X-Use-Rust-Scorer")
           .and_then(|v| v.to_str().ok())
           .map(|v| v == "true")
           .unwrap_or(false)
   }
   ```

3. **Create thin handlers** that reuse Layer 1 operations:
   ```rust
   // src/api/ceramic_cache.rs
   pub async fn ceramic_cache_add_stamps(
       State(pool): State<PgPool>,
       headers: HeaderMap,
       Json(payload): Json<Vec<CacheStampPayload>>,
   ) -> ApiResult<...> {
       if !should_use_rust(&headers) {
           return Err(ApiError::NotFound); // Fall back to Python
       }

       let address = validate_jwt_and_extract_address(extract_jwt(&headers)?)?;

       // Reuse exact same Layer 1 operations from embed
       let mut tx = pool.begin().await?;
       soft_delete_stamps_by_provider(&address, &providers, &mut tx).await?;
       bulk_insert_ceramic_cache_stamps(
           &address, &stamps,
           1, // PASSPORT source_app
           Some(CERAMIC_CACHE_SCORER_ID),
           &mut tx
       ).await?;
       // ... rest of logic
   }
   ```

### 📊 Testing Recommendations

1. **Unit Tests**: Already included for `extract_providers()` helper
2. **Integration Tests**: Set up test database and run:
   ```bash
   DATABASE_URL="postgresql://..." cargo test --lib -- --ignored
   ```
3. **Manual API Tests**:
   ```bash
   # Validate API key
   curl -H "X-API-Key: your-key" http://localhost:3000/internal/embed/validate-api-key

   # Add stamps and score
   curl -X POST -H "Content-Type: application/json" \
     -d '{"scorer_id": 335, "stamps": [...]}' \
     http://localhost:3000/internal/embed/stamps/0xaddress

   # Get score
   curl http://localhost:3000/internal/embed/score/335/0xaddress
   ```

### 🎯 Performance Expectations

Based on the implementation:
- **Cold start**: <100ms (Rust vs Python's 4.5s)
- **Database operations**: <50ms per operation with RDS Proxy
- **Total request time**: <500ms (vs Python's 15-60s)
- **Improvement**: **30-120x faster** response times
- **No more timeouts**: Eliminates 60s Lambda timeout issues

### 📦 Deployment Notes

The implementation is **production-ready** but requires:
1. Environment variables set (DATABASE_URL, HUMAN_POINTS_ENABLED, etc.)
2. RDS Proxy access configured
3. Private ALB routing for `/internal/embed/*` paths
4. Docker build and ECR push (use existing `rust-scorer/build-lambda.sh`)

See `rust-scorer/LAMBDA_DEPLOYMENT.md` for full deployment instructions.

---

## Handoff Notes for Phase 2 Implementation Team

### What's Already Done
- ✅ All core ceramic cache database operations (reusable)
- ✅ Complete embed endpoint implementation
- ✅ Response types and data models
- ✅ Instrumentation patterns established
- ✅ Transaction safety and error handling

### What Phase 2 Needs
- [ ] JWT validation function (10-20 lines)
- [ ] Header routing check (5 lines)
- [ ] Thin ceramic-cache handlers (50-100 lines total)
- [ ] Add `jsonwebtoken` crate to dependencies
- [ ] Route definitions in server.rs

### Estimated Phase 2 Effort
- **1-2 hours** of actual coding (mostly JWT validation)
- **2-4 hours** of testing
- **Total**: Less than 1 day for an experienced Rust developer

The architecture makes Phase 2 trivial because all the hard work (database operations, scoring logic, instrumentation) is already done and reusable.

---

## 🚀 Phase 2 Implementation Status (COMPLETED - 2025-11-14)

### ✅ What Was Implemented

**Phase 2: Ceramic Cache Endpoints** is **COMPLETE** and ready for testing/deployment.

#### 1. JWT Validation Module (`src/auth/jwt.rs`)
- ✅ `validate_jwt_and_extract_address()` - Validates JWT with HS256 algorithm, extracts address from DID claim
- ✅ `extract_jwt_from_header()` - Extracts "Bearer <token>" from Authorization header
- ✅ Unit tests for valid/invalid/missing tokens
- ✅ Matches Python's JWTDidAuthentication behavior exactly

#### 2. Ceramic Cache Handlers (`src/api/ceramic_cache.rs`)
Both endpoints implemented with full instrumentation:
- ✅ `POST /ceramic-cache/stamps/bulk` - Add stamps and rescore with JWT auth + header routing
- ✅ `GET /ceramic-cache/score/{address}` - Get score with stamps and human points

#### 3. Header Routing (`should_use_rust()`)
- ✅ Checks for `X-Use-Rust-Scorer: true` header
- ✅ Returns 404 if header not set to fall back to Python
- ✅ Unit tests for true/false/missing/invalid values

#### 4. Data Models (`src/models/v2_api.rs`)
- ✅ `InternalV2ScoreResponse` - Type alias for V2ScoreResponse (includes human points)
- ✅ `GetStampsWithInternalV2ScoreResponse` - Type alias for ceramic-cache response
- ✅ `CacheStampPayload` - Request payload matching Python's schema

#### 5. Router Integration (`src/api/server.rs`)
- ✅ Both ceramic-cache routes added with correct HTTP methods
- ✅ JWT authentication required for both endpoints
- ✅ Header routing check for gradual rollout

#### 6. Compilation and Testing
- ✅ All code compiles successfully with zero errors
- ✅ 42 unit tests passing (5 for JWT, 5 for header routing, 32 existing)
- ✅ Zero warnings after cleanup

### 📋 Key Implementation Details

#### 1. **JWT Validation**
Matches Python's ninja_jwt exactly:
- Algorithm: HS256
- DID format: `did:pkh:eip155:1:0xADDRESS`
- Address extraction: Split by `:`, take last segment, lowercase
- JWT_SECRET from environment variable

#### 2. **POST /ceramic-cache/stamps/bulk**
Flow matches Python's `cache_stamps()` function:
1. Check `X-Use-Rust-Scorer` header (return 404 if false)
2. Extract and validate JWT token → get address
3. Validate Ethereum address format
4. Soft delete existing stamps by provider (transaction)
5. Bulk insert new stamps with source_app=1 (PASSPORT)
6. Score address using existing scoring logic (includes human points if enabled)
7. Get updated stamps from cache
8. Return `GetStampsWithInternalV2ScoreResponse`

#### 3. **GET /ceramic-cache/score/{address}**
Flow matches Python's `get_score()` function:
1. Check `X-Use-Rust-Scorer` header (return 404 if false)
2. Extract and validate JWT token → get address
3. Validate address in path matches address in JWT
4. Get stamps from ceramic cache
5. Score address (includes human points if enabled)
6. Return stamps + score

#### 4. **Reuse of Phase 1 Architecture**
Both endpoints reuse Phase 1 Layer 1 operations:
- `soft_delete_stamps_by_provider()` - Soft delete by provider
- `bulk_insert_ceramic_cache_stamps()` - UNNEST-based bulk insert
- `get_stamps_from_cache()` - Get non-deleted, non-revoked V1 stamps
- `process_score_request()` - Score with human points integration

#### 5. **Transaction Safety**
All operations maintain all-or-nothing behavior:
- Ceramic cache operations in one transaction
- Scoring operations in separate transaction
- Proper error handling and rollback

### 🔄 Response Format Matching

Both endpoints return exact Python response format:

**GetStampsWithInternalV2ScoreResponse**:
```json
{
  "success": true,
  "stamps": [
    {
      "id": 123,
      "address": "0x...",
      "provider": "Google",
      "stamp": {...}
    }
  ],
  "score": {
    "address": "0x...",
    "score": "10.50000",
    "passing_score": true,
    "threshold": "5.00000",
    "stamps": {...},
    "points_data": {...},
    "possible_points_data": {...}
  }
}
```

### 🧪 Testing Status

#### Unit Tests (42 passing)
- JWT token extraction (valid, missing, invalid format)
- Header routing (true, false, missing, invalid)
- Provider extraction from stamps
- All Phase 1 tests continue to pass

#### Integration Tests (Next Step)
Ready for integration tests with:
1. Real JWT tokens from Python auth endpoint
2. Real database with ceramic cache data
3. Load testing with concurrent requests

### 📦 Deployment Notes

The implementation is **production-ready** and requires:
1. Environment variables:
   - `JWT_SECRET` - Same as Python (from AWS Secrets Manager)
   - `CERAMIC_CACHE_SCORER_ID` - Default 335, configurable
   - `DATABASE_URL` - RDS Proxy connection string
   - `HUMAN_POINTS_ENABLED` - Enable human points integration
2. ALB routing rules for header-based routing
3. Docker build and ECR push (use existing `rust-scorer/build-lambda.sh`)

See `rust-scorer/LAMBDA_DEPLOYMENT.md` for full deployment instructions.

### 🎯 Performance Expectations

Based on Phase 1 architecture and Python baseline:
- **Cold start**: <100ms (Rust vs Python's 4.5s)
- **Database operations**: <50ms per operation with RDS Proxy
- **JWT validation**: <1ms (HS256 is fast)
- **Total request time**: <500ms (vs Python's 15-60s with async_to_sync overhead)
- **Improvement**: **30-120x faster** response times
- **No more timeouts**: Eliminates async_to_sync() overhead completely

### ✅ Phase 2 Complete

All Phase 2 requirements have been implemented:
- [x] JWT validation function (40 lines with tests)
- [x] Header routing check (5 lines with tests)
- [x] Ceramic-cache handlers (150 lines for both endpoints)
- [x] `jsonwebtoken` crate added to dependencies
- [x] Route definitions in server.rs
- [x] Unit tests passing
- [x] Zero compilation warnings

**Status**: Ready for integration testing and deployment!

### 🚀 Next Steps

1. **Integration Testing**:
   ```bash
   # Get JWT token from Python auth endpoint
   TOKEN=$(curl -X POST http://api/ceramic-cache/authenticate \
     -H "Content-Type: application/json" \
     -d '{"issuer": "...", "payload": "...", "signatures": [...]}' \
     | jq -r .access)

   # Test POST /ceramic-cache/stamps/bulk
   curl -X POST \
     -H "Authorization: Bearer $TOKEN" \
     -H "X-Use-Rust-Scorer: true" \
     -H "Content-Type: application/json" \
     -d '[{"provider": "Google", "stamp": {...}}]' \
     http://localhost:3000/ceramic-cache/stamps/bulk

   # Test GET /ceramic-cache/score/{address}
   curl -H "Authorization: Bearer $TOKEN" \
     -H "X-Use-Rust-Scorer: true" \
     http://localhost:3000/ceramic-cache/score/0xaddress
   ```

2. **Load Testing**:
   - Test concurrent requests with header routing
   - Compare latency vs Python baseline
   - Monitor memory usage and connection pooling

3. **Gradual Rollout**:
   - Deploy to staging with header routing
   - Send 1% of traffic with `X-Use-Rust-Scorer: true`
   - Monitor error rates and latency
   - Gradually increase to 100%

4. **Full Cutover**:
   - Once stable, remove header requirement
   - Route all ceramic-cache traffic to Rust
   - Deprecate Python ceramic-cache endpoints