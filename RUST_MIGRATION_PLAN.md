# Rust Migration Plan: Passport Scorer v2/stamps Endpoint

## Executive Summary

This document outlines the migration of the Django-based Passport Scorer API
endpoint `/v2/stamps/{scorerId}/score/{address}` to a high-performance Rust
implementation. The migration aims to achieve 10-100x performance improvement
while maintaining full compatibility with the existing system.

### Key Benefits
- **Response time**: 500-2000ms → 100-150ms
- **Cold starts**: 2-5 seconds → 50ms (AWS Lambda)
- **Memory usage**: 500MB → 50MB
- **Concurrent handling**: 10-100x improvement
- **Cost reduction**: ~40x cheaper per request on Lambda

## Architecture Overview

### Current Django Flow
1. API Gateway → Lambda (Django) → RDS via Django ORM
2. Heavy Celery background processing
3. Multiple database round-trips
4. Python GIL bottleneck for concurrent requests

### New Rust Architecture
```
API Gateway → Lambda (Rust binary) → RDS Proxy → PostgreSQL
```
- Single atomic transaction per request
- True parallelism with Tokio async runtime
- Bulk SQL operations with compile-time validation
- Native credential validation (didkit is already Rust)

## Core Functionality

### What the Endpoint Does

The `/v2/stamps/{scorerId}/score/{address}` endpoint:

1. **Loads existing credentials** from the `ceramic_cache` table
2. **Validates credentials** using cryptographic verification
3. **Applies LIFO deduplication** to prevent stamp reuse across addresses
4. **Calculates a weighted score** based on valid stamps
5. **Persists results** to multiple database tables
6. **Returns score and stamp data** to the client

### Database Operations

#### Tables Involved
- `ceramic_cache` - Source of user credentials (READ)
- `registry_passport` - User passport records (WRITE)
- `registry_stamp` - Validated stamps per passport (WRITE)
- `registry_score` - Calculated scores (WRITE)
- `registry_hashscorerlink` - Deduplication tracking (READ/WRITE)
- `registry_event` - Event tracking for audit (WRITE)
- `account_apikey` - API authentication (READ)
- `account_community` - Community settings (READ)
- `scorer_weighted_binaryweightedscorer` - Scoring weights (READ)
- `human_points_passingscorerecord` - Human points tracking (WRITE)
- `human_points_stampaction` - Stamp verification tracking (WRITE)
- `human_points_bonusaward` - Bonus points awards (WRITE)

#### Write Operations per Request
1. Upsert passport record
2. Delete existing stamps
3. Bulk insert new stamps
4. Upsert score record
5. Bulk upsert hash links for deduplication
6. Insert event records (LIFO dedup + score update)
7. Insert human points records (if enabled):
   - Passing score record
   - Stamp action records
   - Bonus awards (scoring bonus, MetaMask OG)

## Implementation Details

### Dependencies

```toml
[dependencies]
# Web framework
axum = "0.7"
tower = "0.4"
tower-http = { version = "0.5", features = ["trace"] }

# Lambda runtime
lambda_web = "0.2"
lambda_runtime = "0.13"

# Database
sqlx = { version = "0.7", features = [
    "runtime-tokio", "postgres", "json", "chrono", "decimal"
] }

# Async runtime
tokio = { version = "1", features = ["full"] }

# Serialization
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

# Credential validation
didkit = "0.5"  # Already used by Python via FFI

# Utilities
chrono = { version = "0.4", features = ["serde"] }
rust_decimal = { version = "1.32", features = ["serde-float"] }
once_cell = "1.19"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["json"] }

# AWS SDK (optional, for enhanced observability)
aws-config = "1.0"
aws-sdk-cloudwatch = "1.0"
```

### Database Connection with RDS Proxy

```rust
use sqlx::postgres::{PgPoolOptions, PgPool};
use once_cell::sync::OnceCell;
use std::time::Duration;

static DB_POOL: OnceCell<PgPool> = OnceCell::new();

async fn get_pool() -> Result<&'static PgPool> {
    if let Some(pool) = DB_POOL.get() {
        return Ok(pool);
    }
    
    let database_url = std::env::var("RDS_PROXY_URL")?;
    
    let pool = PgPoolOptions::new()
        // Keep low - RDS Proxy handles actual pooling
        .max_connections(5)
        .acquire_timeout(Duration::from_secs(3))
        // Lazy connection for Lambda
        .connect_lazy(&database_url)?;
    
    DB_POOL.set(pool).map_err(|_| "Failed to set pool")?;
    Ok(DB_POOL.get().unwrap())
}
```

### Core Scoring Logic

#### 1. API Key Validation
```rust
async fn validate_api_key(
    headers: &HeaderMap,
    pool: &PgPool
) -> Result<ApiKeyData> {
    let api_key = headers
        .get("X-API-Key")
        .or_else(|| headers.get("Authorization"))
        .ok_or("Missing API key")?;
    
    let key_str = api_key.to_str()?;
    
    // Check against account_apikey table
    let api_key_data = sqlx::query_as!(
        ApiKeyData,
        r#"
        SELECT ak.id, ak.account_id, a.user_id
        FROM account_apikey ak
        JOIN account_account a ON ak.account_id = a.id
        WHERE ak.prefix = $1 AND ak.hashed_key = $2
        "#,
        extract_prefix(key_str),
        hash_key(key_str)
    )
    .fetch_one(pool)
    .await?;
    
    Ok(api_key_data)
}
```

#### 2. Credential Validation
```rust
async fn validate_credentials_batch(
    credentials: &[CeramicCacheRow],
    address: &str
) -> Result<Vec<ValidStamp>> {
    use didkit::{VerifiableCredential, DIDKit};
    
    let mut valid_stamps = Vec::new();
    let did = format!("did:pkh:eip155:1:{}", address);
    
    for cred in credentials {
        let vc: VerifiableCredential = 
            serde_json::from_value(cred.stamp.clone())?;
        
        // Check expiration
        if vc.expiration_date < Utc::now() {
            continue;
        }
        
        // Verify credential signature/proof using didkit
        let verification = 
            DIDKit::verify_credential(&vc, None).await?;
        if verification.errors.is_empty() {
            valid_stamps.push(ValidStamp {
                provider: cred.provider.clone(),
                credential: cred.stamp.clone(),
                nullifiers: extract_nullifiers(&vc),
                expires_at: vc.expiration_date,
            });
        }
    }
    
    Ok(valid_stamps)
}
```

#### 3. LIFO Deduplication
```rust
async fn lifo_dedup(
    stamps: &[ValidStamp],
    address: &str,
    community_id: i32,
    tx: &mut Transaction<'_, Postgres>
) -> Result<(Vec<ValidStamp>, HashMap<String, StampInfo>)> {
    // Extract all nullifiers from stamps
    let all_nullifiers: Vec<String> = stamps
        .iter()
        .flat_map(|s| s.nullifiers.clone())
        .collect();
    
    // Bulk check existing hash links
    let existing_links = sqlx::query!(
        r#"
        SELECT hash, address, expires_at
        FROM registry_hashscorerlink
        WHERE community_id = $1 AND hash = ANY($2)
        "#,
        community_id,
        &all_nullifiers
    )
    .fetch_all(&mut **tx)
    .await?;
    
    // Identify clashing hashes 
    // (owned by other addresses and not expired)
    let mut clashing_hashes = HashSet::new();
    for link in &existing_links {
        if link.address != address 
            && link.expires_at > Utc::now() {
            clashing_hashes.insert(link.hash.clone());
        }
    }
    
    // Filter stamps and prepare hash links for bulk insert
    let mut deduped_stamps = Vec::new();
    let mut clashing_stamps_map = HashMap::new();
    let mut hash_link_data = Vec::new();
    
    for stamp in stamps {
        let has_clash = stamp.nullifiers
            .iter()
            .any(|n| clashing_hashes.contains(n));
        
        if !has_clash {
            deduped_stamps.push(stamp.clone());
            
            for nullifier in &stamp.nullifiers {
                hash_link_data.push((
                    nullifier.clone(),
                    address.to_string(),
                    community_id,
                    stamp.expires_at,
                ));
            }
        } else {
            // Track clashing stamps for event recording
            clashing_stamps_map.insert(
                stamp.provider.clone(),
                StampInfo {
                    nullifiers: stamp.nullifiers.clone(),
                    credential: stamp.credential.clone(),
                }
            );
        }
    }
    
    // Bulk upsert hash links using UNNEST
    if !hash_link_data.is_empty() {
        let hashes: Vec<String> = 
            hash_link_data.iter().map(|h| h.0.clone()).collect();
        let addresses: Vec<String> = 
            hash_link_data.iter().map(|h| h.1.clone()).collect();
        let community_ids: Vec<i32> = 
            hash_link_data.iter().map(|h| h.2).collect();
        let expires_ats: Vec<DateTime<Utc>> = 
            hash_link_data.iter().map(|h| h.3).collect();
        
        sqlx::query!(
            r#"
            INSERT INTO registry_hashscorerlink 
                (hash, address, community_id, expires_at)
            SELECT * FROM UNNEST(
                $1::text[], $2::text[], $3::int[], $4::timestamptz[]
            )
            ON CONFLICT (hash, community_id) 
            DO UPDATE SET 
                address = EXCLUDED.address,
                expires_at = EXCLUDED.expires_at
            WHERE registry_hashscorerlink.expires_at < NOW()
            "#,
            &hashes,
            &addresses,
            &community_ids,
            &expires_ats
        )
        .execute(&mut **tx)
        .await?;
    }
    
    Ok((deduped_stamps, clashing_stamps_map))
}
```

#### 4. Score Calculation
```rust
async fn calculate_score(
    stamps: &[ValidStamp],
    scorer_id: i32,
    tx: &mut Transaction<'_, Postgres>
) -> Result<ScoreData> {
    // Fetch scorer configuration
    let scorer = sqlx::query!(
        r#"
        SELECT weights, threshold 
        FROM scorer_weighted_binaryweightedscorer 
        WHERE scorer_ptr_id = $1
        "#,
        scorer_id
    )
    .fetch_one(&mut **tx)
    .await?;
    
    let weights: HashMap<String, Decimal> = 
        serde_json::from_value(scorer.weights)?;
    let threshold = scorer.threshold;
    
    // Calculate weighted sum (only count each provider once)
    let mut sum = Decimal::from(0);
    let mut stamp_scores = HashMap::new();
    let mut seen_providers = HashSet::new();
    let mut earliest_expiration: Option<DateTime<Utc>> = None;
    
    for stamp in stamps {
        if seen_providers.insert(stamp.provider.clone()) {
            let weight = weights
                .get(&stamp.provider)
                .copied()
                .unwrap_or_default();
            sum += weight;
            
            stamp_scores.insert(stamp.provider.clone(), json!({
                "score": format!("{:.5}", weight),
                "dedup": false,
                "expiration_date": stamp.expires_at
            }));
            
            // Track earliest expiration for score expiration
            match earliest_expiration {
                None => 
                    earliest_expiration = Some(stamp.expires_at),
                Some(exp) if stamp.expires_at < exp => 
                    earliest_expiration = Some(stamp.expires_at),
                _ => {}
            }
        }
    }
    
    // Binary score: 1 if sum >= threshold, 0 otherwise
    let binary_score = if sum >= threshold { 
        Decimal::from(1) 
    } else { 
        Decimal::from(0) 
    };
    
    let evidence = json!({
        "rawScore": sum.to_string(),
        "threshold": threshold.to_string(),
        "success": binary_score == Decimal::from(1)
    });
    
    Ok(ScoreData {
        score: binary_score,
        evidence,
        stamps: serde_json::to_value(stamp_scores)?,
        expiration_date: earliest_expiration,
    })
}
```

#### 5. Event Recording
```rust
async fn record_events(
    address: &str,
    community_id: i32,
    clashing_stamps: &HashMap<String, StampInfo>,
    tx: &mut Transaction<'_, Postgres>
) -> Result<()> {
    // Record LIFO deduplication events
    if !clashing_stamps.is_empty() {
        let mut event_data = Vec::new();
        
        for (provider, stamp_info) in clashing_stamps {
            event_data.push((
                "LIFO_DEDUPLICATION",
                address.to_string(),
                json!({
                    "nullifiers": stamp_info.nullifiers,
                    "provider": provider,
                    "community_id": community_id,
                }),
                community_id,
            ));
        }
        
        // Bulk insert events
        let actions: Vec<String> = 
            event_data.iter().map(|e| e.0.to_string()).collect();
        let addresses: Vec<String> = 
            event_data.iter().map(|e| e.1.clone()).collect();
        let data_values: Vec<JsonValue> = 
            event_data.iter().map(|e| e.2.clone()).collect();
        let community_ids: Vec<i32> = 
            event_data.iter().map(|e| e.3).collect();
        
        sqlx::query!(
            r#"
            INSERT INTO registry_event 
                (action, address, data, community_id, created_at)
            SELECT *, NOW() FROM UNNEST(
                $1::text[], $2::text[], $3::jsonb[], $4::int[]
            )
            "#,
            &actions,
            &addresses,
            &data_values,
            &community_ids
        )
        .execute(&mut **tx)
        .await?;
    }
    
    // Record score update event
    sqlx::query!(
        r#"
        INSERT INTO registry_event 
            (action, address, data, community_id, created_at)
        VALUES ('SCORE_UPDATE', $1, $2, $3, NOW())
        "#,
        address,
        json!({"scorer_id": community_id}),
        community_id
    )
    .execute(&mut **tx)
    .await?;
    
    Ok(())
}
```

#### 6. Human Points Integration (Optional)
```rust
async fn process_human_points(
    address: &str,
    community_id: i32,
    score: &Decimal,
    deduped_stamps: &[ValidStamp],
    tx: &mut Transaction<'_, Postgres>
) -> Result<()> {
    // Check if Human Points is enabled for this community
    let community = sqlx::query!(
        r#"
        SELECT human_points_program 
        FROM account_community 
        WHERE id = $1
        "#,
        community_id
    )
    .fetch_one(&mut **tx)
    .await?;
    
    if !community.human_points_program {
        return Ok(());
    }
    
    // Only process if score is passing (binary score = 1)
    if *score != Decimal::from(1) {
        return Ok(());
    }
    
    // Check timestamp eligibility
    let start_timestamp = std::env::var("HUMAN_POINTS_START_TIMESTAMP")
        .unwrap_or_else(|_| "0".to_string())
        .parse::<i64>()?;
    
    if Utc::now().timestamp() < start_timestamp {
        return Ok(());
    }
    
    // 1. Record passing score for this community
    sqlx::query!(
        r#"
        INSERT INTO human_points_passingscorerecord 
            (address, community_id, created_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (address, community_id) DO NOTHING
        "#,
        address,
        community_id
    )
    .execute(&mut **tx)
    .await?;
    
    // 2. Record stamp actions (which stamps were verified)
    let stamp_providers: Vec<String> = deduped_stamps
        .iter()
        .map(|s| s.provider.clone())
        .collect();
    
    sqlx::query!(
        r#"
        INSERT INTO human_points_stampaction 
            (address, provider, action, created_at)
        SELECT $1, provider, 'VERIFIED', NOW()
        FROM UNNEST($2::text[]) AS provider
        ON CONFLICT (address, provider) DO NOTHING
        "#,
        address,
        &stamp_providers
    )
    .execute(&mut **tx)
    .await?;
    
    // 3. Check and award scoring bonus 
    // (if user has 4+ passing scores across communities)
    let passing_count = sqlx::query_scalar!(
        r#"
        SELECT COUNT(DISTINCT community_id) 
        FROM human_points_passingscorerecord
        WHERE address = $1
        "#,
        address
    )
    .fetch_one(&mut **tx)
    .await?;
    
    if passing_count >= 4 {
        sqlx::query!(
            r#"
            INSERT INTO human_points_bonusaward 
                (address, bonus_type, points, created_at)
            VALUES ($1, 'SCORING_BONUS', 50, NOW())
            ON CONFLICT (address, bonus_type) DO NOTHING
            "#,
            address
        )
        .execute(&mut **tx)
        .await?;
    }
    
    // 4. Check for MetaMask OG bonus
    if deduped_stamps.iter().any(|s| s.provider == "metamaskDeveloperDao") {
        sqlx::query!(
            r#"
            INSERT INTO human_points_bonusaward 
                (address, bonus_type, points, created_at)
            VALUES ($1, 'METAMASK_OG', 100, NOW())
            ON CONFLICT (address, bonus_type) DO NOTHING
            "#,
            address
        )
        .execute(&mut **tx)
        .await?;
    }
    
    Ok(())
}
```

### Complete Endpoint Implementation

```rust
#[instrument(skip(pool))]
async fn score_address(
    Path((scorer_id, address)): Path<(i32, String)>,
    State(pool): State<PgPool>,
    headers: HeaderMap,
) -> Result<Json<V2ScoreResponse>> {
    // Input validation
    let address = address.to_lowercase();
    if !is_valid_eth_address(&address) {
        return Err(ErrorResponse::BadRequest(
            "Invalid address format"
        ));
    }
    
    // API key validation
    let api_key_data = validate_api_key(&headers, &pool).await?;
    
    // Start database transaction for atomicity
    let mut tx = pool.begin().await?;
    
    // 1. Upsert passport record
    let passport_id = sqlx::query_scalar!(
        r#"
        INSERT INTO registry_passport (address, community_id)
        VALUES ($1, $2)
        ON CONFLICT (address, community_id) 
        DO UPDATE SET address = EXCLUDED.address
        RETURNING id
        "#,
        &address,
        scorer_id
    )
    .fetch_one(&mut *tx)
    .await?;
    
    // 2. Load credentials from CeramicCache
    let credentials = sqlx::query!(
        r#"
        SELECT provider, stamp, proof_value, created_at
        FROM ceramic_cache
        WHERE address = $1 AND deleted_at IS NULL
        ORDER BY created_at DESC
        "#,
        &address
    )
    .fetch_all(&mut *tx)
    .await?;
    
    info!(
        address = %address,
        credential_count = credentials.len(),
        "Loaded credentials from cache"
    );
    
    // 3. Validate credentials
    let valid_stamps = 
        validate_credentials_batch(&credentials, &address).await?;
    
    // 4. Apply LIFO deduplication (returns both deduped stamps and clashing stamps)
    let (deduped_stamps, clashing_stamps) = 
        lifo_dedup(&valid_stamps, &address, scorer_id, &mut tx)
            .await?;
    
    info!(
        valid_count = valid_stamps.len(),
        deduped_count = deduped_stamps.len(),
        "Processed stamps"
    );
    
    // 5. Bulk update stamps
    sqlx::query!(
        "DELETE FROM registry_stamp WHERE passport_id = $1", 
        passport_id
    )
    .execute(&mut *tx)
    .await?;
    
    if !deduped_stamps.is_empty() {
        let providers: Vec<String> = deduped_stamps
            .iter()
            .map(|s| s.provider.clone())
            .collect();
        let credentials: Vec<JsonValue> = deduped_stamps
            .iter()
            .map(|s| s.credential.clone())
            .collect();
        
        sqlx::query!(
            r#"
            INSERT INTO registry_stamp 
                (passport_id, provider, credential)
            SELECT $1, * FROM UNNEST($2::text[], $3::jsonb[])
            "#,
            passport_id,
            &providers,
            &credentials
        )
        .execute(&mut *tx)
        .await?;
    }
    
    // 6. Calculate score
    let score_data = 
        calculate_score(&deduped_stamps, scorer_id, &mut tx)
            .await?;
    
    // 7. Persist score
    let score_record = sqlx::query!(
        r#"
        INSERT INTO registry_score (
            passport_id, score, status, last_score_timestamp, 
            evidence, stamps, expiration_date
        )
        VALUES ($1, $2, 'DONE', NOW(), $3, $4, $5)
        ON CONFLICT (passport_id) 
        DO UPDATE SET
            score = EXCLUDED.score,
            status = EXCLUDED.status,
            last_score_timestamp = EXCLUDED.last_score_timestamp,
            evidence = EXCLUDED.evidence,
            stamps = EXCLUDED.stamps,
            expiration_date = EXCLUDED.expiration_date
        RETURNING score, last_score_timestamp, evidence, 
                  stamps, expiration_date
        "#,
        passport_id,
        score_data.score,
        score_data.evidence,
        score_data.stamps,
        score_data.expiration_date
    )
    .fetch_one(&mut *tx)
    .await?;
    
    // 8. Record events
    record_events(&address, scorer_id, &clashing_stamps, &mut tx)
        .await?;
    
    // 9. Process Human Points (if enabled)
    if std::env::var("HUMAN_POINTS_ENABLED")
        .unwrap_or_else(|_| "false".to_string()) == "true" {
        process_human_points(
            &address, 
            scorer_id, 
            &score_data.score,
            &deduped_stamps, 
            &mut tx
        ).await?;
    }
    
    // Commit transaction
    tx.commit().await?;
    
    info!(
        score = %score_data.score,
        "Scoring complete"
    );
    
    // Format response
    Ok(Json(V2ScoreResponse {
        address: address.clone(),
        score: score_record.score.unwrap_or_default(),
        passing_score: score_record.score.unwrap_or_default() 
            >= Decimal::from(1),
        threshold: extract_threshold(&score_record.evidence),
        last_score_timestamp: score_record.last_score_timestamp
            .map(|t| t.to_rfc3339()),
        expiration_timestamp: score_record.expiration_date
            .map(|t| t.to_rfc3339()),
        error: None,
        stamps: score_record.stamps.unwrap_or_default(),
    }))
}
```

## Observability & Monitoring

### Structured Logging with Tracing

```rust
use tracing_subscriber::{fmt, EnvFilter, prelude::*};

pub fn init_tracing() {
    tracing_subscriber::registry()
        .with(
            fmt::layer()
                .json()  // JSON format for CloudWatch
                .with_target(false)
                .with_current_span(true)
                .with_span_list(true)
        )
        .with(EnvFilter::from_default_env())
        .init();
}
```

### CloudWatch Metrics

Key metrics to track:
- Request latency (P50, P95, P99)
- Database query duration
- Credential validation success rate
- Deduplication conflicts
- Score distribution

### Example CloudWatch Insights Queries

```sql
-- Request performance breakdown
fields @timestamp, span, duration_ms
| filter request_id = "abc-123"
| sort @timestamp

-- Slow database queries
fields request_id, operation, duration_ms
| filter operation like /sql/
| filter duration_ms > 100
| sort duration_ms desc

-- Score calculation statistics
filter span = "calculate_score"
| stats avg(duration_ms) as avg_ms,
        max(duration_ms) as max_ms,
        count() as total
```

## Testing Strategy

### Unit Tests
```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_score_calculation() {
        let stamps = vec![
            ValidStamp {
                provider: "Google".to_string(),
                weight: Decimal::from_str("10.5").unwrap(),
                // ...
            },
        ];
        
        let score = calculate_weighted_sum(&stamps, &weights);
        assert_eq!(score, Decimal::from_str("10.5").unwrap());
    }
    
    #[sqlx::test]
    async fn test_deduplication(pool: PgPool) {
        // Test LIFO deduplication logic with real database
    }
}
```

### Integration Tests
```rust
// tests/integration_test.rs
#[tokio::test]
async fn test_full_scoring_flow() {
    let app = create_app().await;
    
    let response = app
        .oneshot(
            Request::get("/v2/stamps/1/score/0x123...")
                .header("X-API-Key", "test_key")
                .body(Body::empty())
                .unwrap()
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::OK);
}
```

### Load Testing
```bash
# Using Artillery or K6
artillery run load-test.yml

# Expected metrics:
# - P95 latency < 200ms
# - 1000+ RPS per Lambda instance
# - 0% error rate under normal load
```

## Deployment Strategy

### Phase 1: Shadow Mode (Week 1-2)
- Deploy Rust Lambda alongside Django
- Route 1% of traffic for comparison
- Monitor performance and accuracy
- No user impact if issues arise

### Phase 2: Gradual Rollout (Week 3-4)
- Increase traffic percentage: 5% → 25% → 50%
- Monitor error rates and latency
- A/B test performance metrics
- Maintain Django as fallback

### Phase 3: Full Migration (Week 5)
- Route 100% traffic to Rust
- Keep Django dormant for rollback
- Monitor for edge cases
- Document any discrepancies

### Lambda Configuration

```yaml
# serverless.yml or SAM template
RustScorerFunction:
  Type: AWS::Lambda::Function
  Properties:
    Runtime: provided.al2
    Handler: bootstrap
    MemorySize: 256  # Start conservative
    Timeout: 30
    Environment:
      Variables:
        RDS_PROXY_URL: !GetAtt RDSProxy.Endpoint
        RUST_LOG: info
        RUST_BACKTRACE: 1
    VpcConfig:
      SecurityGroupIds: 
        - !Ref LambdaSecurityGroup
      SubnetIds: 
        - !Ref PrivateSubnet1
        - !Ref PrivateSubnet2
```

### Build & Deploy

```bash
# Build script
#!/bin/bash
cargo lambda build --release --arm64
cp target/lambda/passport-scorer/bootstrap ./
zip lambda-deployment.zip bootstrap

# Deploy
aws lambda update-function-code \
    --function-name passport-scorer-rust \
    --zip-file fileb://lambda-deployment.zip

# Or using CDK/Terraform
```

## Performance Expectations

### Baseline (Django)
- Cold start: 2-5 seconds
- Warm response: 500-2000ms
- Memory: 512MB minimum
- Concurrent requests: Limited by Python GIL

### Target (Rust)
- Cold start: 50ms
- Warm response: 100-150ms
- Memory: 128-256MB
- Concurrent requests: 1000+ per instance

### Database Impact
- Reduced connection pool pressure (5 connections vs 20+)
- Faster query execution (bulk operations)
- Lower lock contention (single transaction)
- RDS Proxy handles connection multiplexing

## Risk Mitigation

### Potential Issues & Solutions

1. **Credential Validation Differences**
   - Risk: didkit Rust version behaves differently than Python FFI
   - Mitigation: Extensive testing against production data
   - Fallback: Route specific providers to Django if needed

2. **Database Lock Contention**
   - Risk: Bulk operations cause lock conflicts
   - Mitigation: Use appropriate isolation levels
   - Solution: Implement retry logic with exponential backoff

3. **Memory Leaks**
   - Risk: Long-running Lambda accumulates memory
   - Mitigation: Proper connection pool management
   - Solution: Lambda auto-cycles after N requests

4. **Scoring Discrepancies**
   - Risk: Float precision differences Rust vs Python
   - Mitigation: Use Decimal type consistently
   - Testing: Compare scores for 10k+ addresses

## Success Criteria

### Performance Metrics
- [ ] P95 latency < 200ms
- [ ] P99 latency < 500ms
- [ ] Cold start < 100ms
- [ ] Memory usage < 256MB
- [ ] 0% increase in error rate

### Functional Requirements
- [ ] 100% score parity with Django
- [ ] All stamps correctly validated
- [ ] LIFO deduplication working correctly
- [ ] API response format unchanged
- [ ] Database writes atomic and consistent

### Operational Goals
- [ ] CloudWatch logs properly structured
- [ ] Alerts configured for anomalies
- [ ] Rollback procedure documented
- [ ] Team trained on Rust debugging

## Team Resources

### Required Expertise
- **Rust Developer**: Core implementation
- **DevOps Engineer**: Lambda deployment and monitoring
- **Database Admin**: Query optimization and RDS Proxy config
- **QA Engineer**: Testing and validation

### Learning Resources
- [Rust Async Book](https://rust-lang.github.io/async-book/)
- [SQLx Documentation](https://github.com/launchbadge/sqlx)
- [AWS Lambda Rust Runtime](
    https://github.com/awslabs/aws-lambda-rust-runtime)
- [Axum Web Framework](https://github.com/tokio-rs/axum)

### Support Channels
- Internal Slack: #rust-migration
- GitHub Issues: passport-scorer-rust
- AWS Support: Performance optimization

## Timeline

### Week 1-2: Development
- Set up Rust project structure
- Implement core scoring logic
- Add comprehensive tests
- Local testing with production data

### Week 3-4: Integration
- Deploy to staging environment
- Integration testing
- Performance benchmarking
- Shadow mode deployment

### Week 5-6: Rollout
- Gradual traffic migration
- Monitor and optimize
- Document findings
- Full cutover

### Week 7-8: Cleanup
- Remove Django endpoint
- Optimize Lambda configuration
- Final documentation
- Team knowledge transfer

## Conclusion

This migration represents a significant performance improvement opportunity
with manageable risk. The Rust implementation will provide:

1. **10-100x faster response times**
2. **Dramatically reduced infrastructure costs**
3. **Better scalability for future growth**
4. **Improved developer experience with type safety**

The key to success is thorough testing, gradual rollout, and maintaining the
ability to rollback quickly if issues arise.