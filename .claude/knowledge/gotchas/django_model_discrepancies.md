# Django Model Field Discrepancies

## [2025-09-10] Django Model Field Verification

When implementing Phase 2 of the Rust migration, discovered several discrepancies between expected Django model fields and actual fields:

### Key Discrepancies Found

1. **CeramicCache**: Has many additional fields not in Rust model:
   - proof_value, type, compose_db fields
   - issuance_date, expiration_date, source fields
   - These may not be needed for scoring functionality

2. **BinaryWeightedScorer**: 
   - Inherits from Scorer, doesn't have created_at/updated_at directly
   - Actual fields: scorer_ptr_id (FK to Scorer), weights (JSONField), threshold (DecimalField)

3. **HashScorerLink**: 
   - **Critical**: Does NOT have created_at/updated_at fields in Django
   - Only has: hash, community (FK), address, expires_at
   - Has unique_together constraint on hash+community

4. **AccountAPIKey**: 
   - Has rate limit fields not in Rust model: rate_limit, analysis_rate_limit, embed_rate_limit
   - Missing historical_endpoint field

5. **Community**: 
   - Has account (FK), deleted_at fields
   - Has created_at but NOT updated_at

6. **Customization**: 
   - Has scorer field as OneToOneField to Community, not community_id
   - Has many more fields for UI customization

### Impact

The Rust models were created based on what SQL queries expect, but some fields added (like created_at/updated_at on HashScorerLink) don't actually exist in Django models. This could cause runtime SQL errors when querying non-existent columns.

### Resolution Required

Need to align Rust Django model structs with actual Django model definitions to avoid SQL errors.

## [2025-11-13] Confirmed Django Table Schema

Phase 7 testing confirmed the actual Django database schema differs from initial assumptions:

- **registry_passport**: Has only id, address, community_id (NO created_at/updated_at fields)
- **registry_stamp**: Has only id, passport_id, provider, credential (NO timestamps)
- **registry_hashscorerlink**: Has only hash, community, address, expires_at (NO created_at/updated_at)
- **account_community**: Has only created_at (nullable), NO updated_at field

These fields must not be included in INSERT/UPDATE queries or model structs.

See: `rust-scorer/src/models/django.rs`, `rust-scorer/src/db/write_ops.rs`, `api/ceramic_cache/models.py`, `api/scorer_weighted/models.py`, `api/registry/models.py`, `api/account/models.py`