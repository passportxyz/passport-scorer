# Future Data Architecture: Stamps & Scoring

## Vision

This document outlines a simplified, performant data architecture for the Passport scoring system. It represents an ideal end state that prioritizes:

- **Simplicity** - Fewer tables, clearer relationships
- **Performance** - Sub-5ms queries at scale
- **Auditability** - Complete history of all changes
- **Flexibility** - Easy to query both current and historical data

## Core Design Principles

1. **Event-Driven History** - Every scoring is an immutable event with complete context
2. **Soft Deletes** - Never lose data; mark as deleted instead
3. **Snapshots over JOINs** - Store data how it's accessed
4. **Single Source of Truth** - Each piece of data has one authoritative location

## Data Model

### 1. Stamps Table (Full History)

The authoritative record of all stamps ever issued to users.

```sql
CREATE TABLE stamps (
    id BIGSERIAL PRIMARY KEY,
    address TEXT NOT NULL,
    provider TEXT NOT NULL,
    credential JSONB NOT NULL,
    nullifiers TEXT[] NOT NULL,
    
    -- Temporal fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ DEFAULT NULL,  -- NULL = active
    expires_at TIMESTAMPTZ NOT NULL,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',  -- Flexible field for future needs
    
    -- Constraints
    CONSTRAINT unique_active_stamp 
        UNIQUE (address, provider, deleted_at),
    
    -- Indexes for performance
    INDEX idx_active_stamps 
        ON stamps (address, deleted_at) 
        WHERE deleted_at IS NULL,
    
    INDEX idx_provider_lookup 
        ON stamps (address, provider, deleted_at) 
        WHERE deleted_at IS NULL,
    
    INDEX idx_nullifier_search 
        ON stamps USING GIN (nullifiers) 
        WHERE deleted_at IS NULL,
    
    INDEX idx_expiration 
        ON stamps (expires_at) 
        WHERE deleted_at IS NULL
);
```

### 2. Scoring Events Table (Immutable History)

Complete record of every scoring calculation ever performed.

```sql
CREATE TABLE scoring_events (
    id BIGSERIAL PRIMARY KEY,
    address TEXT NOT NULL,
    community_id INT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Scoring results
    score DECIMAL(3,1) NOT NULL,  -- Binary: 0.0 or 1.0
    threshold DECIMAL(10,5) NOT NULL,
    raw_score DECIMAL(10,5) NOT NULL,  -- Sum of weights
    
    -- Complete snapshot at time of scoring
    stamps_snapshot JSONB NOT NULL,  -- Full stamp data used
    weights JSONB NOT NULL,  -- Weights configuration used
    
    -- Metadata
    scorer_version TEXT NOT NULL,  -- Track algorithm changes
    metadata JSONB DEFAULT '{}',  -- Additional context
    
    -- Expiration (earliest stamp expiration)
    expires_at TIMESTAMPTZ,
    
    -- Indexes for performance
    INDEX idx_current_score 
        ON scoring_events (address, community_id, timestamp DESC),
    
    INDEX idx_community_history 
        ON scoring_events (community_id, timestamp DESC),
    
    INDEX idx_address_history 
        ON scoring_events (address, timestamp DESC)
) PARTITION BY RANGE (timestamp);

-- Partition by quarter for better performance
CREATE TABLE scoring_events_2024_q1 PARTITION OF scoring_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
-- etc...
```

### 3. Nullifier Claims Table (Deduplication)

Tracks which address owns which nullifier for LIFO deduplication.

```sql
CREATE TABLE nullifier_claims (
    nullifier TEXT NOT NULL,
    community_id INT NOT NULL,
    address TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (nullifier, community_id),
    
    INDEX idx_address_claims 
        ON nullifier_claims (address, community_id),
    
    INDEX idx_expiration 
        ON nullifier_claims (expires_at)
);

-- Periodic cleanup of expired claims
CREATE INDEX idx_expired_claims 
    ON nullifier_claims (expires_at) 
    WHERE expires_at < NOW();
```

### 4. Weight Configurations (Versioned)

Track how scoring weights change over time.

```sql
CREATE TABLE weight_configs (
    id SERIAL PRIMARY KEY,
    community_id INT NOT NULL,
    version INT NOT NULL,
    weights JSONB NOT NULL,
    threshold DECIMAL(10,5) NOT NULL,
    
    effective_from TIMESTAMPTZ NOT NULL,
    effective_until TIMESTAMPTZ,  -- NULL = currently active
    created_by TEXT,
    reason TEXT,  -- Why weights changed
    
    UNIQUE (community_id, version),
    
    INDEX idx_active_config 
        ON weight_configs (community_id, effective_from, effective_until)
);
```

## Data Flow

### Writing: Stamp Refresh Flow

```python
async def refresh_stamp(address: str, provider: str, new_credential: dict):
    async with db.transaction():
        # 1. Soft delete existing stamp
        await db.execute("""
            UPDATE stamps 
            SET deleted_at = NOW() 
            WHERE address = $1 
              AND provider = $2 
              AND deleted_at IS NULL
        """, address, provider)
        
        # 2. Insert new stamp
        await db.execute("""
            INSERT INTO stamps 
                (address, provider, credential, nullifiers, expires_at)
            VALUES ($1, $2, $3, $4, $5)
        """, address, provider, new_credential, 
            new_credential['nullifiers'], 
            new_credential['expirationDate'])
```

### Writing: Scoring Flow

```python
async def score_passport(address: str, community_id: int):
    async with db.transaction():
        # 1. Get active stamps
        stamps = await db.fetch("""
            SELECT * FROM stamps 
            WHERE address = $1 
              AND deleted_at IS NULL 
              AND expires_at > NOW()
        """, address)
        
        # 2. Check nullifier claims (LIFO dedup)
        valid_stamps = await apply_lifo_dedup(stamps, community_id)
        
        # 3. Calculate score
        weights = await get_current_weights(community_id)
        score_result = calculate_score(valid_stamps, weights)
        
        # 4. Record immutable event
        await db.execute("""
            INSERT INTO scoring_events 
                (address, community_id, score, threshold, raw_score,
                 stamps_snapshot, weights, expires_at, scorer_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, address, community_id, 
            score_result.binary_score,
            score_result.threshold,
            score_result.raw_score,
            Json(valid_stamps),
            Json(weights),
            score_result.expires_at,
            SCORER_VERSION)
        
        # 5. Update nullifier claims
        await update_nullifier_claims(valid_stamps, address, community_id)
```

### Reading: Current Score (Page Load)

```sql
-- Single index lookup, no JOINs, ~1-2ms
SELECT 
    score,
    threshold,
    stamps_snapshot,
    expires_at,
    timestamp
FROM scoring_events
WHERE address = $1 
  AND community_id = $2
ORDER BY timestamp DESC
LIMIT 1;
```

### Reading: Score History

```sql
-- User's score over time
SELECT 
    timestamp,
    score,
    raw_score,
    threshold
FROM scoring_events
WHERE address = $1 
  AND community_id = $2
ORDER BY timestamp DESC
LIMIT 100;
```

### Reading: Time Travel Query

```sql
-- What was the user's score on Jan 1, 2024?
SELECT * FROM scoring_events
WHERE address = $1 
  AND community_id = $2
  AND timestamp <= '2024-01-01'
ORDER BY timestamp DESC
LIMIT 1;
```

## Performance Characteristics

### Storage Estimates (2M users)

```yaml
stamps:
  - 30 stamps/user average
  - 60M total rows (with history)
  - ~30GB storage

scoring_events:
  - 10 scorings/user/year
  - 20M rows/year
  - ~10GB/year (with snapshots)

nullifier_claims:
  - 2 nullifiers/stamp average  
  - 10M active rows
  - ~1GB storage
```

### Query Performance Targets

```yaml
Current Score Lookup:
  - p50: < 1ms
  - p99: < 5ms
  - Index: idx_current_score

Score History (100 records):
  - p50: < 5ms
  - p99: < 20ms
  - Index: idx_address_history

Stamp Refresh:
  - p50: < 10ms
  - p99: < 50ms
  - Operations: 1 UPDATE + 1 INSERT

Full Scoring:
  - p50: < 50ms
  - p99: < 200ms
  - Most time in dedup logic
```

## Key Benefits

### 1. Simplicity
- Only 4 core tables (vs 10+ currently)
- Clear ownership and relationships
- No complex JOINs for common queries

### 2. Performance
- Current score is a single index lookup
- No JOIN penalties as data grows
- Partitioning keeps queries fast forever

### 3. Auditability
- Complete history in stamps table
- Every scoring event preserved
- Can reconstruct state at any point in time

### 4. Flexibility
- JSONB allows schema evolution
- Metadata fields for future needs
- Time travel queries are trivial

## Migration Path (High Level)

1. **Phase 1**: Deploy new tables alongside existing
2. **Phase 2**: Dual write to both systems
3. **Phase 3**: Migrate reads to new tables
4. **Phase 4**: Backfill historical data
5. **Phase 5**: Deprecate old tables

## Open Questions for Refinement

1. **Partitioning Strategy**: By month vs quarter vs year?
2. **Archival**: Move old events to cold storage after N months?
3. **Caching Layer**: Redis for current scores or trust DB performance?
4. **Event Streaming**: Publish scoring events to Kafka/Kinesis?
5. **Analytics**: Separate OLAP copy or query production directly?

## Next Steps

This design represents an ideal end state. The implementation team should:

1. Validate assumptions about access patterns
2. Prototype with production data volumes
3. Benchmark critical query paths
4. Design detailed migration plan
5. Consider interim steps that provide value quickly

## Appendix: Example Queries

### Find Users with Specific Stamp
```sql
SELECT DISTINCT address 
FROM stamps
WHERE provider = 'Google'
  AND deleted_at IS NULL
  AND expires_at > NOW();
```

### Community Statistics
```sql
SELECT 
    DATE_TRUNC('day', timestamp) as day,
    COUNT(DISTINCT address) as unique_users,
    AVG(score) as avg_score,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY score) as median_score
FROM scoring_events
WHERE community_id = $1
  AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1;
```

### Deduplication Conflicts
```sql
-- Find stamps that were deduplicated
SELECT 
    se.address,
    se.timestamp,
    stamp->>'provider' as provider,
    stamp->>'dedup' as was_deduped
FROM scoring_events se,
     jsonb_array_elements(se.stamps_snapshot) as stamp
WHERE se.community_id = $1
  AND (stamp->>'dedup')::boolean = true
  AND se.timestamp > NOW() - INTERVAL '24 hours';
```