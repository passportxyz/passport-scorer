### [14:31] [gotcha] Timestamp serialization precision Python vs Rust
**Details**: Python's Django datetime serialization defaults to milliseconds precision (%.3f) in ISO 8601 format, while Rust's chrono::DateTime serializes with full microseconds precision (%.6f). When migrating Python APIs to Rust, timestamps must use custom serializers to match Python's milliseconds-only precision.

Example fix:
```rust
fn serialize_datetime_millis<S>(dt: &Option<DateTime<Utc>>, serializer: S) -> Result<S::Ok, S::Error>
where S: Serializer {
    match dt {
        Some(dt) => {
            let formatted = dt.format("%Y-%m-%dT%H:%M:%S%.3fZ").to_string();
            serializer.serialize_str(&formatted)
        }
        None => serializer.serialize_none(),
    }
}
```

This affected the Check Bans endpoint where end_time was serializing with microseconds instead of milliseconds.
**Files**: rust-scorer/src/domain/bans.rs
---

### [14:31] [gotcha] PostgreSQL numeric type serialization
**Details**: PostgreSQL numeric(78,0) fields (integers stored as NUMERIC) are read by SQLx as rust_decimal::Decimal type, not as integers. When the Python API returns these as JSON integers, Rust must convert Decimal to i64 explicitly.

Example fix for last_updated_in_block field:
```rust
// Schema field type
pub struct StakeSchema {
    pub last_updated_in_block: i64,  // Not String!
}

// Conversion from database Decimal
last_updated_in_block: s.last_updated_in_block.to_string()
    .parse::<i64>()
    .unwrap_or(0)
```

Converting to String first then parsing to i64 handles the Decimal → i64 conversion correctly. Simply calling .to_i64() on Decimal doesn't work for all cases.
**Files**: rust-scorer/src/domain/stakes.rs, rust-scorer/src/db/queries/stakes.rs
---

