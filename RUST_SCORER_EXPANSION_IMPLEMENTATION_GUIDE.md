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

### Phase 1: Internal Scoring Endpoint (Quick Win)

#### 1.1 Add Internal Score Endpoint
**File**: `rust-scorer/src/api/server.rs`

```rust
// Add new route without API key requirement
.route("/internal/score/{scorer_id}/{address}", get(internal_score_handler))
```

**File**: `rust-scorer/src/api/handler.rs`

```rust
#[tracing::instrument(
    skip(state, headers),
    fields(scorer_id = scorer_id, address = %address, is_internal = true)
)]
pub async fn internal_score_handler(
    Path((scorer_id, address)): Path<(i64, String)>,  // Note: i64 not i32!
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, ApiError> {
    // Validate internal secret from header
    let secret = headers
        .get("X-Internal-Secret")
        .and_then(|v| v.to_str().ok())
        .ok_or(ApiError::Unauthorized)?;

    if secret != std::env::var("INTERNAL_SECRET").unwrap_or_default() {
        return Err(ApiError::Unauthorized);
    }

    // Reuse existing scoring logic
    let score = score_address_internal(scorer_id, &address, &state.pool).await?;

    Ok(Json(score))
}
```

**Environment Variable**: Add `INTERNAL_SECRET` to Lambda configuration

### Phase 2: Embed Endpoints

#### 2.1 Rate Limit Check Endpoint
**Endpoint**: `GET /internal/embed/validate-api-key`

```rust
#[tracing::instrument(
    skip(state, headers),
    fields(endpoint = "validate_api_key")
)]
pub async fn validate_api_key_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, ApiError> {
    // Extract API key from header
    let api_key = extract_api_key(&headers)?;

    // Validate and get key data (reuse existing code)
    let key_data = validate_api_key(&api_key, &state.pool).await?;

    // Return rate limit info
    Ok(Json(json!({
        "embed_rate_limit": key_data.embed_rate_limit
    })))
}
```

#### 2.2 Add Stamps and Score Endpoint
**Endpoint**: `POST /internal/embed/stamps/{address}`

```rust
#[derive(Deserialize)]
pub struct AddStampsPayload {
    scorer_id: i32,
    stamps: Vec<serde_json::Value>,
}

#[derive(Serialize)]
pub struct StampsWithScoreResponse {
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

    // 1. Soft delete existing stamps (V1 only)
    sqlx::query!(
        "UPDATE ceramic_cache
         SET deleted_at = NOW(), updated_at = NOW()
         WHERE address = $1 AND provider = ANY($2) AND type = 'V1' AND deleted_at IS NULL",
        &address,
        &providers_from_stamps(&payload.stamps)
    )
    .execute(&mut *tx)
    .await?;

    // 2. Insert new stamps
    for stamp in &payload.stamps {
        insert_ceramic_cache_stamp(&address, stamp, &mut tx).await?;
    }

    // 3. Score the address
    let score = score_address_internal(
        payload.scorer_id,
        &address,
        &state.pool
    ).await?;

    // 4. Get updated stamps
    let stamps = get_stamps_from_cache(&address, &mut tx).await?;

    tx.commit().await?;

    Ok(Json(StampsWithScoreResponse {
        success: true,
        stamps,
        score,
    }))
}
```

### Phase 3: Ceramic Cache Endpoints with JWT

#### 3.1 JWT Validation
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

#### 3.2 Ceramic Cache Endpoints
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

### Phase 4: Database Operations

#### 4.1 Ceramic Cache Table Operations
**File**: `rust-scorer/src/db/ceramic_cache.rs`

```rust
#[derive(sqlx::FromRow, Serialize)]
pub struct CachedStamp {
    pub id: i32,
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
        INSERT INTO ceramic_cache (
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

pub async fn get_stamps_from_cache(
    address: &str,
    pool: &PgPool,
) -> Result<Vec<CachedStamp>, DatabaseError> {
    let stamps = sqlx::query_as!(
        CachedStamp,
        r#"
        SELECT id, address, provider, stamp, created_at
        FROM ceramic_cache
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

```bash
# Add to Lambda configuration
DATABASE_URL=postgresql://user:pass@rds-proxy.amazonaws.com/dbname
INTERNAL_SECRET=random-secret-string
JWT_SECRET=your-jwt-secret  # Same as Python
CERAMIC_CACHE_SCORER_ID=335  # Or your scorer ID
HUMAN_POINTS_ENABLED=true
RUST_LOG=info
```

## Testing Checklist

### Unit Tests
```bash
cd rust-scorer
cargo test --lib
```

### Integration Tests
```bash
# Test internal scoring
curl -H "X-Internal-Secret: $SECRET" \
  http://localhost:3000/internal/score/335/0xaddress

# Test JWT auth
TOKEN=$(curl -X POST http://python-api/ceramic-cache/authenticate | jq -r .token)
curl -H "Authorization: Bearer $TOKEN" \
  -H "X-Use-Rust-Scorer: true" \
  http://localhost:3000/ceramic-cache/score/0xaddress

# Test embed endpoints
curl -X POST -H "Content-Type: application/json" \
  -d '{"scorer_id": 335, "stamps": [...]}' \
  http://localhost:3000/internal/embed/stamps/0xaddress
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

## Questions to Answer Before Starting

1. What is the JWT_SECRET value? (Get from Python settings)
2. What is the CERAMIC_CACHE_SCORER_ID? (Usually 335)
3. What is the RDS Proxy endpoint? (Get from AWS console)
4. Do we need to support all stamp types? (Start with V1)

## Final Note

This implementation fixes the root cause of the performance issues: Django's `async_to_sync()` creating new event loops for every request. By moving to Rust, we eliminate this overhead entirely and get 30-120x performance improvement.