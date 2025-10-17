# Database Field Types


## Primary Key Types Across Tables

Many Django tables use BIGINT (i64) for primary keys and foreign keys, not INT4 (i32) as initially assumed. This affects:

- passport_id fields
- score_id fields  
- community_id fields
- account_id fields

All database operations must use the correct i64 type to avoid type mismatches.

See `rust-scorer/src/db/write_ops.rs`, `rust-scorer/src/api/handler.rs`