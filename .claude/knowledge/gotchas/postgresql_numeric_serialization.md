# PostgreSQL Numeric Type Serialization

## [2025-11-21] PostgreSQL numeric(78,0) to JSON Integer Conversion

PostgreSQL numeric(78,0) fields (integers stored as NUMERIC) are read by SQLx as rust_decimal::Decimal type, not as integers. When the Python API returns these as JSON integers, Rust must convert Decimal to i64 explicitly.

### Problem

The stake_stake table's last_updated_in_block field is defined as numeric(78,0) in PostgreSQL. SQLx reads this as Decimal, but the API needs to return it as an integer.

### Solution

Convert Decimal to String first, then parse to i64:

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

### Why Not `.to_i64()`?

Simply calling `.to_i64()` on Decimal doesn't work for all cases. Converting to String first then parsing to i64 handles the Decimal → i64 conversion correctly.

See: `rust-scorer/src/domain/stakes.rs`, `rust-scorer/src/db/queries/stakes.rs`