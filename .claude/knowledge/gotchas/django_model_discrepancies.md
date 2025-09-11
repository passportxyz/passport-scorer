# Django Model Field Discrepancies

## Confirmed Django Table Schema

The actual Django database schema differs from initial assumptions:

- **registry_passport**: Has only id, address, community_id (NO created_at/updated_at fields)
- **registry_stamp**: Has only id, passport_id, provider, credential (NO timestamps)
- **registry_hashscorerlink**: Has only hash, community, address, expires_at (NO created_at/updated_at)
- **account_community**: Has only created_at (nullable), NO updated_at field

These fields must not be included in INSERT/UPDATE queries or model structs.

See: `rust-scorer/src/models/django.rs`, `rust-scorer/src/db/write_ops.rs`, `api/ceramic_cache/models.py`, `api/scorer_weighted/models.py`, `api/registry/models.py`, `api/account/models.py`