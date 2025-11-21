# Timestamp Serialization Precision

## [2025-11-21] Python vs Rust Timestamp Precision

Python's Django datetime serialization defaults to milliseconds precision (%.3f) in ISO 8601 format, while Rust's chrono::DateTime serializes with full microseconds precision (%.6f). When migrating Python APIs to Rust, timestamps must use custom serializers to match Python's milliseconds-only precision.

### Solution

Use custom serializer for DateTime fields:

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

### Affected Endpoints

This affected the Check Bans endpoint where end_time was serializing with microseconds instead of milliseconds, causing comparison test failures.

See: `rust-scorer/src/domain/bans.rs`