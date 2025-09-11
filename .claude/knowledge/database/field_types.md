# Database Field Types

## AccountAPIKey Table Field Types

The account_accountapikey table has specific field types that differ from initial assumptions:

- **id**: VARCHAR(150) - not INT (inherited from djangorestframework-api-key's AbstractAPIKey model which uses CharField)
- **account_id**: BIGINT (i64) - not INT4 (i32)

These field types are crucial for proper database compatibility in the Rust models.

See `rust-scorer/src/models/django.rs`, `rust-scorer/src/auth/api_key.rs`

## Primary Key Types Across Tables

Many Django tables use BIGINT (i64) for primary keys and foreign keys, not INT4 (i32) as initially assumed. This affects:

- passport_id fields
- score_id fields  
- community_id fields
- account_id fields

All database operations must use the correct i64 type to avoid type mismatches.

See `rust-scorer/src/db/write_ops.rs`, `rust-scorer/src/api/handler.rs`