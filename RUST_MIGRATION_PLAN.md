# Rust Migration Plan: Passport Scorer v2/stamps Endpoint

## Executive Summary

This document outlines the migration of the Django-based Passport Scorer API
endpoint `/v2/stamps/{scorerId}/score/{address}` to a high-performance Rust
implementation. The migration aims to achieve 10-100x performance improvement
while maintaining full compatibility with the existing system.

**Important**: This POC maintains exact database operation parity with Python
to ensure accurate performance comparison. All DB reads/writes match Django's
patterns to isolate Rust/Python language performance differences.

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

### Simplifications from Python Implementation

1. **Nullifiers Only**: Only support `credentialSubject.nullifiers` array field (no legacy `hash` field)
2. **No Feature Flags**: Always process all nullifiers (no FF_MULTI_NULLIFIER filtering)
3. **Required Array**: All credentials must have 1+ nullifiers in the array
4. **Django Compatibility**: Must write exact same data to existing Django tables

### Database Operations

#### Tables Involved
- `ceramic_cache` - Source of user credentials (READ)
  - Filter: `deleted_at IS NULL AND revocation IS NULL`
  - Select latest stamp per provider by `updated_at`
- `registry_passport` - User passport records (WRITE)
  - Upsert with `ON CONFLICT (address, community_id)`
- `registry_stamp` - Validated stamps per passport (WRITE)
  - DELETE all, then bulk INSERT new stamps
- `registry_score` - Calculated scores (WRITE)
  - Must populate: score, status, evidence, stamp_scores, stamps, expiration_date
  - See "Django Compatibility" section for exact field formats
- `registry_hashscorerlink` - Deduplication tracking (READ/WRITE)
  - Bulk upsert with retry logic for concurrent requests
- `registry_event` - Event tracking for audit (WRITE)
  - LIFO_DEDUPLICATION events for clashing stamps
  - SCORE_UPDATE event (must be created after score save)
- `account_apikey` - API authentication (READ)
- `account_community` - Community settings (READ)
- `scorer_weighted_binaryweightedscorer` - Scoring weights (READ)
- `account_customization` - Custom weights per community (READ)
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

### Clean Internal Models Architecture

To facilitate future migration to the simplified data architecture while maintaining Django compatibility, 
the implementation uses clean internal models with translation layers:

```rust
// Clean internal models aligned with future architecture
#[derive(Debug, Clone, Serialize, Deserialize)]
struct StampData {
    provider: String,
    credential: Value,
    nullifiers: Vec<String>,
    expires_at: DateTime<Utc>,
    weight: Decimal,
    was_deduped: bool,
}

#[derive(Debug)]
struct ScoringResult {
    address: String,
    community_id: i32,
    binary_score: Decimal,
    raw_score: Decimal,  
    threshold: Decimal,
    valid_stamps: Vec<StampData>,
    deduped_stamps: Vec<StampData>,
    expires_at: Option<DateTime<Utc>>,
    timestamp: DateTime<Utc>,
}

// V2 API Response types (matching Python schema)
#[derive(Serialize)]
struct V2StampScoreResponse {
    score: String,
    dedup: bool,
    expiration_date: Option<String>,
}

#[derive(Serialize)]
struct V2ScoreResponse {
    address: String,
    score: Option<String>,  // Formatted with 5 decimals
    passing_score: bool,
    threshold: String,  // Formatted with 5 decimals
    last_score_timestamp: Option<String>,
    expiration_timestamp: Option<String>,
    error: Option<String>,
    stamps: HashMap<String, V2StampScoreResponse>,
    // Optional fields for Human Points
    // points_data: Option<PointsData>,
    // possible_points_data: Option<PointsData>,
}

// Translation layer for Django compatibility
impl ScoringResult {
    // Convert to V2 API response format
    fn to_v2_response(&self) -> V2ScoreResponse {
        let mut stamps = HashMap::new();
        
        // Add valid stamps with their weights
        for stamp in &self.valid_stamps {
            stamps.insert(stamp.provider.clone(), V2StampScoreResponse {
                score: format!("{:.5}", stamp.weight),
                dedup: false,
                expiration_date: Some(stamp.expires_at.to_rfc3339()),
            });
        }
        
        // Add deduped stamps with zero score
        for stamp in &self.deduped_stamps {
            stamps.insert(stamp.provider.clone(), V2StampScoreResponse {
                score: "0.00000".to_string(),
                dedup: true,
                expiration_date: Some(stamp.expires_at.to_rfc3339()),
            });
        }
        
        V2ScoreResponse {
            address: self.address.clone(),
            score: Some(format!("{:.5}", self.binary_score)),
            passing_score: self.binary_score >= Decimal::from(1),
            threshold: format!("{:.5}", self.threshold),
            last_score_timestamp: Some(self.timestamp.to_rfc3339()),
            expiration_timestamp: self.expires_at.map(|t| t.to_rfc3339()),
            error: None,
            stamps,
        }
    }
    
    // Convert to Django database fields
    fn to_django_score_fields(&self) -> DjangoScoreFields {
        let mut stamp_scores = HashMap::new();
        
        // Only valid stamps go in stamp_scores (for scoring logic)
        for stamp in &self.valid_stamps {
            stamp_scores.insert(stamp.provider.clone(), stamp.weight.to_f64().unwrap());
        }
        
        DjangoScoreFields {
            score: self.binary_score,
            status: "DONE".to_string(),
            last_score_timestamp: self.timestamp,
            expiration_date: self.expires_at,
            error: None,
            evidence: json!({
                "type": "ThresholdScoreCheck",
                "success": self.binary_score == Decimal::from(1),
                "rawScore": self.raw_score.to_string(),
                "threshold": self.threshold.to_string()
            }),
            stamp_scores: serde_json::to_value(stamp_scores).unwrap(),
            stamps: self.to_v2_response().stamps, // Reuse V2 format
        }
    }
    
    // Future: Convert to single event row for new architecture
    fn to_scoring_event(&self) -> ScoringEvent {
        ScoringEvent {
            address: self.address.clone(),
            community_id: self.community_id,
            score: self.binary_score,
            threshold: self.threshold,
            raw_score: self.raw_score,
            stamps_snapshot: json!({
                "valid": &self.valid_stamps,
                "deduped": &self.deduped_stamps,
            }),
            weights: self.valid_stamps.iter()
                .map(|s| (s.provider.clone(), s.weight))
                .collect(),
            expires_at: self.expires_at,
            timestamp: self.timestamp,
            scorer_version: env!("CARGO_PKG_VERSION"),
        }
    }
}

// Future architecture types (for dual-writing preparation)
#[derive(Debug)]
struct ScoringEvent {
    address: String,
    community_id: i32,
    score: Decimal,
    threshold: Decimal,
    raw_score: Decimal,
    stamps_snapshot: Value,
    weights: HashMap<String, Decimal>,
    expires_at: Option<DateTime<Utc>>,
    timestamp: DateTime<Utc>,
    scorer_version: String,
}
```

This clean model architecture provides:
1. **Separation of concerns** - Core logic works with clean models, not Django quirks
2. **Future-ready** - Easy transition to event-driven architecture
3. **Type safety** - Rust's type system ensures correct transformations
4. **Single source of truth** - One model generates all output formats

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

### Django Compatibility Requirements

The clean internal models translate to Django's expected table formats. The `DjangoScoreFields` struct 
shows the exact fields that must be populated in the `registry_score` table:

#### Critical Django Behaviors to Maintain

1. **Score Update Event**: Django creates SCORE_UPDATE event via pre_save signal when status="DONE"
   - Rust must manually create this event after saving score

2. **Deduped Stamps in Response**: 
   - Appear in `stamps` dict with score="0.00000" and dedup=true
   - Do NOT appear in `stamp_scores` or have weight=0

3. **Provider Deduplication in Scoring**:
   - Only first stamp per provider contributes weight
   - Subsequent stamps with same provider get score=0

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

#### 2. Credential Validation (Simplified)
```rust
async fn validate_credentials_batch(
    credentials: &[CeramicCacheRow],
    address: &str
) -> Result<Vec<ValidStamp>> {
    use didkit::{VerifiableCredential, DIDKit};
    
    let mut valid_stamps = Vec::new();
    let did = format!("did:pkh:eip155:1:{}", address.to_lowercase());
    
    for cred in credentials {
        let vc: VerifiableCredential = 
            serde_json::from_value(cred.stamp.clone())?;
        
        // Check expiration
        if vc.expiration_date < Utc::now() {
            continue;
        }
        
        // Verify issuer is trusted
        if !TRUSTED_IAM_ISSUERS.contains(&vc.issuer) {
            continue;
        }
        
        // Validate required fields
        let cs = &vc.credential_subject;
        
        // IMPORTANT: Only support nullifiers array (no hash field)
        let nullifiers = cs.get("nullifiers")
            .and_then(|n| n.as_array())
            .ok_or("Missing nullifiers array")?;
        
        if nullifiers.is_empty() {
            continue; // Must have at least 1 nullifier
        }
        
        // Verify DID matches
        if cs.get("id").and_then(|id| id.as_str())
            .map(|id| id.to_lowercase() != did)
            .unwrap_or(true) {
            continue;
        }
        
        // Verify credential signature/proof using didkit
        let verification = DIDKit::verify_credential(
            &json!(vc).to_string(),
            r#"{"proofPurpose":"assertionMethod"}"#
        ).await?;
        
        let verification: serde_json::Value = 
            serde_json::from_str(&verification)?;
        
        if verification["errors"].as_array()
            .map(|e| e.is_empty()).unwrap_or(false) {
            valid_stamps.push(ValidStamp {
                provider: cs["provider"].as_str().unwrap().to_string(),
                credential: cred.stamp.clone(),
                nullifiers: nullifiers.iter()
                    .filter_map(|n| n.as_str())
                    .map(|s| s.to_string())
                    .collect(),
                expires_at: vc.expiration_date,
            });
        }
    }
    
    Ok(valid_stamps)
}
```

#### 3. LIFO Deduplication (Simplified - Nullifiers Only)
```rust
async fn lifo_dedup(
    stamps: &[ValidStamp],
    address: &str,
    community_id: i32,
    tx: &mut Transaction<'_, Postgres>
) -> Result<(Vec<ValidStamp>, HashMap<String, StampInfo>)> {
    const MAX_RETRIES: u8 = 5;
    let mut retry_count = 0;
    
    loop {
        match lifo_dedup_attempt(stamps, address, community_id, tx).await {
            Ok(result) => return Ok(result),
            Err(e) if is_integrity_error(&e) && retry_count < MAX_RETRIES => {
                retry_count += 1;
                continue; // Retry on concurrent hash link conflicts
            }
            Err(e) => return Err(e),
        }
    }
}

async fn lifo_dedup_attempt(
    stamps: &[ValidStamp],
    address: &str,
    community_id: i32,
    tx: &mut Transaction<'_, Postgres>
) -> Result<(Vec<ValidStamp>, HashMap<String, StampInfo>)> {
    // Extract ALL nullifiers from stamps (no filtering)
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
    
    let now = Utc::now();
    let mut clashing_hashes = HashSet::new();
    let mut expired_hashes = HashSet::new();
    let mut owned_hashes = HashSet::new();
    
    for link in &existing_links {
        if link.address == address {
            owned_hashes.insert(link.hash.clone());
        } else if link.expires_at > now {
            clashing_hashes.insert(link.hash.clone());
        } else {
            expired_hashes.insert(link.hash.clone());
        }
    }
    
    let mut deduped_stamps = Vec::new();
    let mut clashing_stamps_map = HashMap::new();
    let mut hash_links_to_create = Vec::new();
    let mut hash_links_to_update = Vec::new();
    
    for stamp in stamps {
        // Stamp is deduped if ANY nullifier clashes
        let clashing_nullifiers: Vec<_> = stamp.nullifiers
            .iter()
            .filter(|n| clashing_hashes.contains(*n))
            .collect();
        
        if clashing_nullifiers.is_empty() {
            // No clashes - stamp is valid
            deduped_stamps.push(stamp.clone());
            
            for nullifier in &stamp.nullifiers {
                if owned_hashes.contains(nullifier) {
                    // Already owned, maybe update expiration
                    hash_links_to_update.push((
                        nullifier.clone(),
                        address.to_string(),
                        community_id,
                        stamp.expires_at,
                    ));
                } else if expired_hashes.contains(nullifier) {
                    // Take over expired link
                    hash_links_to_update.push((
                        nullifier.clone(),
                        address.to_string(),
                        community_id,
                        stamp.expires_at,
                    ));
                } else {
                    // Create new link
                    hash_links_to_create.push((
                        nullifier.clone(),
                        address.to_string(),
                        community_id,
                        stamp.expires_at,
                    ));
                }
            }
        } else {
            // Has clashes - stamp is deduped
            clashing_stamps_map.insert(
                stamp.provider.clone(),
                StampInfo {
                    nullifiers: stamp.nullifiers.clone(), // ALL nullifiers
                    credential: stamp.credential.clone(),
                }
            );
            
            // IMPORTANT: Backfill non-clashing nullifiers with clashing owner's data
            let first_clash = clashing_nullifiers[0];
            let clash_owner = existing_links.iter()
                .find(|l| &l.hash == first_clash)
                .unwrap();
            
            for nullifier in &stamp.nullifiers {
                if !clashing_hashes.contains(nullifier) && 
                   !owned_hashes.contains(nullifier) {
                    // Backfill with clashing owner's data
                    hash_links_to_create.push((
                        nullifier.clone(),
                        clash_owner.address.clone(),
                        community_id,
                        clash_owner.expires_at,
                    ));
                }
            }
        }
    }
    
    // Bulk operations for hash links
    if !hash_links_to_create.is_empty() {
        let hashes: Vec<_> = hash_links_to_create.iter().map(|h| &h.0).collect();
        let addresses: Vec<_> = hash_links_to_create.iter().map(|h| &h.1).collect();
        let community_ids: Vec<_> = hash_links_to_create.iter().map(|h| h.2).collect();
        let expires_ats: Vec<_> = hash_links_to_create.iter().map(|h| h.3).collect();
        
        sqlx::query!(
            r#"
            INSERT INTO registry_hashscorerlink 
                (hash, address, community_id, expires_at)
            SELECT * FROM UNNEST(
                $1::text[], $2::text[], $3::int[], $4::timestamptz[]
            )
            "#,
            &hashes[..], &addresses[..], &community_ids[..], &expires_ats[..]
        )
        .execute(&mut **tx)
        .await?;
    }
    
    if !hash_links_to_update.is_empty() {
        // Update expired or owned links
        for (hash, addr, comm_id, expires) in &hash_links_to_update {
            sqlx::query!(
                r#"
                UPDATE registry_hashscorerlink 
                SET address = $1, expires_at = $2
                WHERE hash = $3 AND community_id = $4
                "#,
                addr, expires, hash, comm_id
            )
            .execute(&mut **tx)
            .await?;
        }
    }
    
    // Verify expected number of links were created/updated
    let expected_count = hash_links_to_create.len() + hash_links_to_update.len();
    let actual_count = sqlx::query_scalar!(
        r#"
        SELECT COUNT(*) 
        FROM registry_hashscorerlink
        WHERE address = $1 AND community_id = $2 
            AND hash = ANY($3)
        "#,
        address,
        community_id,
        &all_nullifiers
    )
    .fetch_one(&mut **tx)
    .await?: Option<i64>;
    
    if actual_count != Some(expected_count as i64) {
        return Err("Unexpected number of hash links".into());
    }
    
    Ok((deduped_stamps, clashing_stamps_map))
}
```

#### 4. Score Calculation with Clean Models
```rust
async fn build_scoring_result(
    address: &str,
    community_id: i32,
    deduped_stamps: &[ValidStamp],
    clashing_stamps: &HashMap<String, StampInfo>,
    tx: &mut Transaction<'_, Postgres>
) -> Result<ScoringResult> {
    // Fetch scorer configuration
    let scorer = sqlx::query!(
        r#"
        SELECT weights, threshold 
        FROM scorer_weighted_binaryweightedscorer 
        WHERE scorer_ptr_id = $1
        "#,
        community_id
    )
    .fetch_one(&mut **tx)
    .await?;
    
    let weights: HashMap<String, Decimal> = 
        serde_json::from_value(scorer.weights)?;
    let threshold = scorer.threshold;
    
    // Build clean stamp data
    let mut valid_stamps = Vec::new();
    let mut deduped_stamps_data = Vec::new();
    let mut sum = Decimal::from(0);
    let mut seen_providers = HashSet::new();
    let mut earliest_expiration: Option<DateTime<Utc>> = None;
    
    // Process valid stamps
    for stamp in deduped_stamps {
        if seen_providers.insert(stamp.provider.clone()) {
            let weight = weights
                .get(&stamp.provider)
                .copied()
                .unwrap_or_default();
            sum += weight;
            
            valid_stamps.push(StampData {
                provider: stamp.provider.clone(),
                credential: stamp.credential.clone(),
                nullifiers: stamp.nullifiers.clone(),
                expires_at: stamp.expires_at,
                weight,
                was_deduped: false,
            });
            
            // Track earliest expiration
            match earliest_expiration {
                None => 
                    earliest_expiration = Some(stamp.expires_at),
                Some(exp) if stamp.expires_at < exp => 
                    earliest_expiration = Some(stamp.expires_at),
                _ => {}
            }
        }
    }
    
    // Process deduped stamps
    for (provider, stamp_info) in clashing_stamps {
        deduped_stamps_data.push(StampData {
            provider: provider.clone(),
            credential: stamp_info.credential.clone(),
            nullifiers: stamp_info.nullifiers.clone(),
            expires_at: Utc::now(), // Use current time or fetch from DB
            weight: Decimal::from(0),
            was_deduped: true,
        });
    }
    
    // Binary score: 1 if sum >= threshold, 0 otherwise
    let binary_score = if sum >= threshold { 
        Decimal::from(1) 
    } else { 
        Decimal::from(0) 
    };
    
    Ok(ScoringResult {
        address: address.to_string(),
        community_id,
        binary_score,
        raw_score: sum,
        threshold,
        valid_stamps,
        deduped_stamps: deduped_stamps_data,
        expires_at: earliest_expiration,
        timestamp: Utc::now(),
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

Using the clean internal models, the endpoint implementation becomes clearer and more maintainable:

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
    
    // 6. Build clean scoring result
    let scoring_result = build_scoring_result(
        &address,
        scorer_id,
        &deduped_stamps,
        &clashing_stamps,
        &mut tx
    ).await?;
    
    // 7. Persist score using Django format
    let django_fields = scoring_result.to_django_score_fields();
    let score_record = sqlx::query!(
        r#"
        INSERT INTO registry_score (
            passport_id, score, status, last_score_timestamp, 
            evidence, stamps, stamp_scores, expiration_date
        )
        VALUES ($1, $2, $3, NOW(), $4, $5, $6, $7)
        ON CONFLICT (passport_id) 
        DO UPDATE SET
            score = EXCLUDED.score,
            status = EXCLUDED.status,
            last_score_timestamp = EXCLUDED.last_score_timestamp,
            evidence = EXCLUDED.evidence,
            stamps = EXCLUDED.stamps,
            stamp_scores = EXCLUDED.stamp_scores,
            expiration_date = EXCLUDED.expiration_date
        RETURNING score, last_score_timestamp, evidence, 
                  stamps, expiration_date
        "#,
        passport_id,
        django_fields.score,
        django_fields.status,
        django_fields.evidence,
        serde_json::to_value(&django_fields.stamps)?,
        django_fields.stamp_scores,
        django_fields.expiration_date
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
            &scoring_result.binary_score,
            &scoring_result.valid_stamps, 
            &mut tx
        ).await?;
    }
    
    // Commit transaction
    tx.commit().await?;
    
    info!(
        score = %scoring_result.binary_score,
        "Scoring complete"
    );
    
    // Return clean V2 response
    Ok(Json(scoring_result.to_v2_response()))
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

## Implementation Verification Checklist

### 1. Data Loading from CeramicCache
- [ ] Filter by `deleted_at IS NULL AND revocation IS NULL`
- [ ] Select latest stamp per provider using `updated_at`
- [ ] Handle case-insensitive address matching
- [ ] Parse credential JSON correctly

### 2. Credential Validation (Nullifiers Only)
- [ ] Extract nullifiers from `credentialSubject.nullifiers` array
- [ ] Reject credentials without nullifiers array or with empty array
- [ ] Verify DID format: `did:pkh:eip155:1:{address}` (lowercase)
- [ ] Check issuer is in TRUSTED_IAM_ISSUERS list
- [ ] Verify expiration date is in future (timezone-aware)
- [ ] Call didkit with exact JSON format and `proofPurpose="assertionMethod"`
- [ ] Match credentialSubject.id with expected DID (case-insensitive)

### 3. LIFO Deduplication
- [ ] Process ALL nullifiers (no v0 filtering)
- [ ] Implement 5-retry mechanism for IntegrityError
- [ ] Check if ANY nullifier in stamp clashes with existing hash links
- [ ] Handle expired hash links (can be reassigned)
- [ ] Backfill non-clashing nullifiers when some clash
- [ ] Verify expected count of hash links after operations
- [ ] Use bulk INSERT with UNNEST for performance

### 4. Score Calculation
- [ ] Only first stamp per provider contributes weight
- [ ] Check for Customization model weight overrides
- [ ] Calculate binary score: 1 if sum >= threshold, else 0
- [ ] Use Decimal type with proper precision (5 decimal places)
- [ ] Set score expiration to earliest stamp expiration

### 5. Django Table Compatibility
- [ ] registry_passport: Upsert with ON CONFLICT
- [ ] registry_stamp: DELETE all, then bulk INSERT
- [ ] registry_score fields:
  - [ ] `score`: Binary decimal (0 or 1)
  - [ ] `status`: "DONE" for success
  - [ ] `evidence`: JSON with type, success, rawScore, threshold
  - [ ] `stamp_scores`: Provider -> weight mapping
  - [ ] `stamps`: Provider -> {score, dedup, expiration_date}
  - [ ] `expiration_date`: Earliest stamp expiration
- [ ] Include deduped stamps in `stamps` with score="0.00000"

### 6. Event Recording
- [ ] Create LIFO_DEDUPLICATION events for clashing stamps
  - [ ] Include all nullifiers in event data
  - [ ] Set community field on event
- [ ] Create SCORE_UPDATE event after score save
  - [ ] Include serialized score in data
  - [ ] Set community field on event

### 7. Human Points Integration
- [ ] Check if enabled and score == 1
- [ ] Verify timestamp >= HUMAN_POINTS_START_TIMESTAMP
- [ ] Record passing score with ON CONFLICT DO NOTHING
- [ ] Record stamp actions for all valid stamps
- [ ] Award scoring bonus if 4+ passing communities
- [ ] Check for MetaMask OG bonus ("metamaskDeveloperDao")

### 8. API Response Format
- [ ] Return V2ScoreResponse structure
- [ ] Format scores with 5 decimal places in stamps dict
- [ ] Set passing_score boolean based on score >= 1
- [ ] Use ISO 8601 for all timestamps
- [ ] Include both valid and deduped stamps in response

### 9. Database Operations
- [ ] All operations in single atomic transaction
- [ ] Maintain exact same operation order as Python
- [ ] Use same indexes and query patterns
- [ ] Handle concurrent requests properly

### 10. Performance Targets
- [ ] P95 latency < 200ms
- [ ] P99 latency < 500ms
- [ ] Cold start < 100ms
- [ ] Memory usage < 256MB
- [ ] 0% increase in error rate

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

## Implementation Notes for Development Team

### Critical Points

1. **Nullifiers Simplification**: 
   - Only support `nullifiers` array field (no `hash` field)
   - No feature flag filtering - process ALL nullifiers
   - Credentials must have 1+ nullifiers

2. **Clean Models Architecture**:
   - Use `ScoringResult` as the core internal model
   - Translate to Django format only at database boundaries
   - Keep V2 API response generation separate from DB logic
   - This prepares for future event-driven architecture

3. **Django Compatibility**:
   - Must write exact same data structure to existing tables
   - Don't forget the SCORE_UPDATE event (Django creates via signal)
   - The `to_django_score_fields()` method handles all quirks

4. **Future Migration Path**:
   - Clean models align with future `scoring_events` table
   - Add feature flag for dual-writing when ready
   - The `to_scoring_event()` method is ready for future use
   - Minimal code changes needed for migration

5. **Exact DB Parity**:
   - This POC maintains all DB operations to isolate language performance
   - Don't optimize DB access patterns yet - match Django exactly
   - Future iterations can optimize after proving base performance

6. **Testing Priority**:
   - LIFO deduplication with concurrent requests
   - Exact score calculation matching
   - Django table field formats vs clean model translation
   - Event creation
   - V2 API response format

## Conclusion

This migration represents a significant performance improvement opportunity
with manageable risk. The Rust implementation will provide:

1. **10-100x faster response times**
2. **Dramatically reduced infrastructure costs**
3. **Better scalability for future growth**
4. **Improved developer experience with type safety**

The key to success is thorough testing, gradual rollout, and maintaining the
ability to rollback quickly if issues arise. The simplifications (nullifiers-only,
no feature flags) make the implementation cleaner while maintaining compatibility
with modern credentials.