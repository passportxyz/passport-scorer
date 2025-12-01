# Code Comments TODO

This file lists knowledge that should be added as code comments in the Rust scorer codebase.

## 1. Type Conversion Requirements

**File**: `rust-scorer/src/domain/scoring.rs`
**Line**: ~491 (at ValidatedCredential → ValidStamp conversion)

**Comment to add**:
```rust
// Type conversions at module boundaries:
// 1. ValidatedCredential → ValidStamp: From auth module to scoring model
// 2. StampData → ValidStamp: From LIFO result for bulk_insert_stamps
// 3. StampData → StampInfo: For insert_dedup_events conversion
// Each module uses optimized types for its purpose, requiring translation at boundaries.
```

**File**: `rust-scorer/src/models/translation.rs`
**Line**: ~56 (at DjangoScoreFields.stamps HashMap conversion)

**Comment to add**:
```rust
// DjangoScoreFields.stamps must be HashMap<String, DjangoStampScore>, not JSON value.
// This ensures proper serialization for Django compatibility.
```

---

## 2. Timestamp Serialization Fix

**File**: `rust-scorer/src/domain/bans.rs`
**Line**: 1 (above `serialize_datetime_millis` function)

**Comment to add**:
```rust
/// Custom serializer for DateTime fields to match Python's milliseconds precision.
///
/// Python's Django datetime serialization defaults to milliseconds (%.3f) in ISO 8601 format,
/// while Rust's chrono::DateTime serializes with microseconds (%.6f). This serializer ensures
/// compatibility by formatting timestamps with exactly 3 decimal places (milliseconds only).
///
/// Without this, comparison tests would fail due to precision mismatches.
```

---

## 3. PostgreSQL Numeric Serialization

**File**: `rust-scorer/src/domain/stakes.rs`
**Line**: ~42 (at Decimal to i64 conversion point)

**Comment to add**:
```rust
// PostgreSQL numeric(78,0) fields are read by SQLx as rust_decimal::Decimal, not integers.
// Convert to String first, then parse to i64 for proper handling of large integers.
// Simply calling .to_i64() doesn't work correctly for all cases.
last_updated_in_block: s.last_updated_in_block
    .to_string()
    .parse::<i64>()
    .unwrap_or(0)
```

---

## 4. AddStampsPayload Type Flexibility

**File**: `rust-scorer/src/models/v2_api.rs`
**Line**: ~122 (above AddStampsPayload struct or deserializer)

**Comment to add**:
```rust
/// AddStampsPayload accepts scorer_id as either string or integer for API compatibility.
/// This handles clients that send scorer_id in different formats (JSON integer vs JSON string).
/// The handler code explicitly calls parse_scorer_id() to convert to i64, making the
/// type conversion visible rather than implicit like Python's Pydantic coercion.
```

---

## Status

These comments should be added by the development team to improve code documentation and explain non-obvious implementation decisions.
