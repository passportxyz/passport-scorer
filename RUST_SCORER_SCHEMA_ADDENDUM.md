# Rust Scorer Implementation - Schema Addendum

## Correct Table Names & Types from Actual Schema

### Table Names (Django adds prefixes)
- `ceramic_cache_ceramiccache` (not `ceramic_cache`)
- `registry_hashscorerlink`
- `registry_passport`
- `registry_score`
- `registry_stamp`
- `account_accountapikey`

### Primary Key Types
Use `i64` for all ID fields, not `i32`:
```rust
pub struct DjangoScore {
    pub id: i64,  // NOT i32
    pub passport_id: i64,
    // ...
}
```

### API Key Table Specifics
```rust
pub struct DjangoApiKey {
    pub id: String,  // VARCHAR(150) - UUID format
    pub prefix: String,
    pub hashed_key: String,
    pub hashed_key_sha256: Option<String>,  // VARCHAR(71)
    pub account_id: i64,
    pub embed_rate_limit: Option<String>,
    // ...
}
```

### Ceramic Cache Schema
```rust
pub struct CeramicCacheStamp {
    pub id: i64,
    pub address: Option<String>,  // Can be NULL
    pub provider: String,
    pub stamp: serde_json::Value,
    pub type_: i32,  // 1 for V1
    pub deleted_at: Option<DateTime<Utc>>,
    pub compose_db_save_status: String,  // "pending"
    pub proof_value: String,
    pub source_app: Option<i32>,
    pub source_scorer_id: Option<i64>,
    // ...
}
```

### Human Points Provider Field
```rust
// Provider field is NOT NULL but Django converts None to ""
// When inserting with no provider, use empty string:
let provider = stamp_provider.unwrap_or_else(|| "".to_string());
```

### Scorer Config Tables
Check both tables for backwards compatibility:
```rust
// Try BinaryWeightedScorer first
let config = sqlx::query!(
    "SELECT weights, threshold FROM scorer_weighted_binaryweightedscorer WHERE scorer_ptr_id = $1",
    scorer_id
).fetch_optional(pool).await?;

// Fall back to WeightedScorer if not found
let config = match config {
    Some(c) => c,
    None => sqlx::query!(
        "SELECT weights, threshold FROM scorer_weighted_weightedscorer WHERE scorer_ptr_id = $1",
        scorer_id
    ).fetch_one(pool).await?
};
```

### Missing Timestamps
These tables don't have created_at/updated_at:
- `registry_passport`
- `registry_stamp`
- `registry_hashscorerlink` (only has expires_at)
- `account_community` (only has created_at, no updated_at)

Don't try to insert/update these fields.

## Type Mappings Summary

| PostgreSQL | Rust Type |
|------------|-----------|
| bigint | i64 |
| integer | i32 |
| character varying(n) | String |
| text | String |
| boolean | bool |
| timestamp with time zone | DateTime<Utc> |
| jsonb | serde_json::Value |
| numeric(18,9) | Decimal |
| numeric(10,5) | Decimal |

That's the main stuff that wasn't in the original guide. The schema is pretty straightforward otherwise.