# Django Model Field Discrepancies

## Confirmed Django Table Schema

The actual Django database schema differs from initial assumptions:

- **registry_passport**: Has only id, address, community_id (NO created_at/updated_at fields)
- **registry_stamp**: Has only id, passport_id, provider, credential (NO timestamps)
- **registry_hashscorerlink**: Has only hash, community, address, expires_at (NO created_at/updated_at)
- **account_community**: Has only created_at (nullable), NO updated_at field

These fields must not be included in INSERT/UPDATE queries or model structs.

## [2025-10-20] CeramicCache Nullable Timestamps

The ceramic_cache_ceramiccache table has nullable timestamp fields that can cause "unexpected null" errors when querying:

- **created_at**: nullable (null=True in Django model)
- **updated_at**: marked as null=False in Django but can be NULL for old records or migration issues

The Rust DjangoCeramicCache struct must have both fields as Option<DateTime<Utc>> to handle potential NULL values in the database. This error often occurs when scoring new addresses that might have incomplete data or when dealing with legacy records.

See: `rust-scorer/src/models/django.rs`, `rust-scorer/src/db/write_ops.rs`, `api/ceramic_cache/models.py`, `api/scorer_weighted/models.py`, `api/registry/models.py`, `api/account/models.py`