# Development Gotchas

Tricky behaviors, misconceptions, and non-obvious issues encountered during development.

## Nullifier Handling

The Python `get_nullifiers` function in `lifo.py` has a feature flag `FF_MULTI_NULLIFIER` that controls whether all nullifiers are used or only v0-prefixed ones:
- When OFF (default): only nullifiers starting with 'v0' are used for deduplication
- The nullifiers come from `credential.credentialSubject.nullifiers` array or `.hash` field

The Rust implementation simplifies this:
- Only supports the nullifiers array field (not the legacy hash field)
- Always processes ALL nullifiers in the array without any v0 prefix filtering
- All credentials must have `credentialSubject.nullifiers` as an array with 1+ values

Python LIFO implementation complexity (includes both hash and nullifiers fields, with 5-retry mechanism for concurrent IntegrityError handling, backfilling logic for partial clashes, and reassignment of expired hash links). See `api/account/deduplication/lifo.py`.

## Score Update Event Data Structure

The SCORE_UPDATE event in Django is created via a pre_save signal on the Score model when status="DONE". The event data contains the serialized Score model using Django's `serializers.serialize("json", [score])`:

```json
[{
  "model": "registry.score",
  "pk": <primary_key>,
  "fields": {
    "passport": <passport_id>,
    "score": "decimal_value",
    "last_score_timestamp": "ISO timestamp",
    "status": "DONE",
    "error": null,
    "evidence": {...},
    "stamp_scores": {...},
    "stamps": {...},
    "expiration_date": "ISO timestamp"
  }
}]
```

See `api/registry/models.py`.

## Django Table Schema Discrepancies

The actual Django database schema differs from initial assumptions:

- **registry_passport**: Has only id, address, community_id (NO created_at/updated_at fields)
- **registry_stamp**: Has only id, passport_id, provider, credential (NO timestamps)
- **registry_hashscorerlink**: Has only hash, community, address, expires_at (NO created_at/updated_at)
- **account_community**: Has only created_at (nullable), NO updated_at field

These fields must not be included in INSERT/UPDATE queries or model structs. See `rust-scorer/src/models/django.rs`, `rust-scorer/src/db/write_ops.rs`, `api/ceramic_cache/models.py`, `api/scorer_weighted/models.py`, `api/registry/models.py`, `api/account/models.py`.

## Score Calculation Implementation

### Weight Lookup with Customization Support
The load_scorer_config function checks for customization overrides first via load_customization, then falls back to base scorer weights. Customization uses custom weights but still takes threshold from base scorer.

### Binary Score Calculation
Exactly matches Python - returns Decimal(1) if raw_score >= threshold, else Decimal(0). Uses >= operator for threshold comparison (not just >).

### Decimal Type with Proper Precision
All weights and scores use rust_decimal::Decimal type for exact precision matching Python's Decimal. Needs 5 decimal place formatting when converting to API response.

### Earliest Expiration Tracking
Tracks the earliest expires_at timestamp from all valid stamps to set the score's expiration date.

See `rust-scorer/src/scoring/calculation.rs`.

## Scorer ID vs Community ID Naming

CRITICAL: The API uses "scorer_id" but the database uses "community_id" for the same value. This is a historical artifact from when they planned 1:many communities:scorers, but it's actually 1:1.

- **API endpoint**: `/v2/stamps/{scorer_id}/score/{address}` 
- **Database queries**: Use community_id = scorer_id value from API
- **scorer_weighted_binaryweightedscorer table**: Uses scorer_ptr_id which maps to community.id
- **registry_passport, registry_hashscorerlink, etc**: Use community_id

The Python code handles this by using the scorer_id from the API as community_id in database queries. The Rust code needs to do the same. See `rust-scorer/src/db/read_ops.rs`, `rust-scorer/src/api/handler.rs`.

## Human Points Provider Field Handling

The registry_humanpoints table provider field is defined as NOT NULL in the database, but Django's CharField with `null=False` has special NULL handling behavior:

- When Django saves a record with `provider=None`, it automatically converts to empty string `''`
- This is Django ORM's default behavior for CharField fields with null=False
- The database constraint allows empty strings but not NULL values

Rust implementation must match this Django behavior by using empty strings `""` instead of NULL for provider field.

### Affected Actions

Actions that should use empty string provider:
- **SCORING_BONUS (SCB)**: Empty string provider
- **METAMASK_OG (MTA)**: Empty string provider

Actions that use actual provider names:
- **HUMAN_KEYS (HKY)**: Provider from stamp
- **IDENTITY_STAKING_* (ISB/ISS/ISG)**: Provider from stamp
- **COMMUNITY_STAKING_* (CSB/CSE/CST)**: Provider from stamp
- **HUMAN_TECH_* stamps**: Provider from stamp

See `rust-scorer/src/human_points/processing.rs`, `api/registry/models.py`.

## Ceramic Cache V2 Never Implemented

The ceramic_cache table has a type field with enum values V1 and V2, but V2 stamps were never actually implemented. All Python code exclusively uses CeramicCache.StampType.V1.

For the Rust scorer expansion:
- Always filter for `type = 'V1'` in ceramic_cache queries
- Don't implement V2 support as it's not needed
- Can hardcode V1 type filtering in database queries

See `api/ceramic_cache/api/v1.py`, `api/ceramic_cache/models.py`, `RUST_SCORER_EXPANSION_IMPLEMENTATION_GUIDE.md`.

## Custom Platform Admin Bugs

### CustomPlatformAdmin search_display bug

The `CustomPlatformAdmin` class in `api/account/admin.py` has `search_display` instead of `search_fields`. This is a silent bug introduced in commit 310d718 (Sep 16 2024, PR #673). Django ignores `search_display` as it is not a recognized ModelAdmin attribute, meaning admin search for CustomPlatform has been broken since introduction. The adjacent `CustomCredentialRulesetAdmin` correctly uses `search_fields`.

### CustomPlatform.is_evm hardcoded False

The `get_custom_stamps()` method hardcodes `'isEVM': False` on all platforms. When adding the `is_evm` BooleanField to CustomPlatform, this line must be updated to use `platform.is_evm` instead. This is critical for NFT stamps which require `isEVM=True` to signal the frontend that on-chain verification is needed.

See `api/account/models.py`.

## Rust Scorer Missing Customization Dynamic Weights

The Rust scorer's `load_scorer_config()` in `domain/scoring.rs` does NOT merge customization dynamic weights from the `account_customcredential` and `account_allowlist` tables.

The Python implementation (`scorer_weighted/computation.py:39-43`) calls `customization.get_customization_dynamic_weights()` which:
1. Queries `account_customcredential` table for custom credential weights
2. Queries `account_allowlist` table for allow list weights
3. Merges both into the scorer weights dict

**Impact**: Any custom credentials (DeveloperList, NFT, etc.) and allow list weights are IGNORED in the Rust scoring path.

**Current Risk**: Production currently routes 0% to Rust, so no immediate impact. This MUST be fixed before increasing Rust traffic for communities with custom credentials.

**Fix Required**: Add calls in Rust's scoring config loading to:
1. Query `account_customcredential` → `account_customcredentialruleset` for provider_id and weight
2. Query `account_allowlist` → `account_addresslistmember` for allow list weights
3. Merge these into the weights dict before scoring

See `rust-scorer/src/domain/scoring.rs`, `api/scorer_weighted/computation.py`, `api/account/models.py`.

## Django BooleanField AddField PostgreSQL Behavior

Django `AddField` with `BooleanField(default=False)` generates:
```sql
ALTER TABLE ADD COLUMN field BOOLEAN DEFAULT false NOT NULL;
ALTER TABLE ALTER COLUMN field DROP DEFAULT;
```

On PostgreSQL 11+, `ADD COLUMN` with a non-volatile DEFAULT does NOT cause a table rewrite. The default is stored in `pg_attribute.attmissingval` catalog. Django immediately drops the DEFAULT in the same transaction, but both operations are fast (metadata-only).

**Result**: Effectively zero-downtime safe for non-volatile defaults like `BooleanField(default=False)` on PostgreSQL 11+.

**Warning**: For PostgreSQL < 11, this WOULD cause a full table rewrite and lock.

See `api/account/models.py`.

## TRUSTED_IAM_ISSUERS Environment Variable

The Rust scorer correctly loads TRUSTED_IAM_ISSUERS from the environment variable (as a JSON array) instead of using hardcoded values, matching the Python implementation.

Implementation details:
- Uses OnceLock for lazy initialization and caching
- Fallback to default values if the env var is not set or fails to parse
- Defaults match Python's settings.base.py defaults

Format: `TRUSTED_IAM_ISSUERS='["did:key:...", "did:ethr:0x..."]'`

This ensures the Rust implementation maintains parity with Python's dynamic configuration approach. See `rust-scorer/src/auth/credentials.rs`, `api/scorer/settings/base.py`.

## WeightConfiguration CSV Optional Field

The WeightConfiguration model has an optional csv_source FileField. The admin's save_model() method was causing a ValueError "The 'csv_source' attribute has no file associated with it" when saving without a CSV file.

**Fix Applied**:

1. **In save_model()**: Check if obj.csv_source exists AND has a 'file' attribute before processing CSV
2. **In clean_csv_source()**: Return early if no csv_source is provided (it's optional)

This allows WeightConfiguration to be created either:
- **With a CSV file**: Auto-populates WeightConfigurationItems from CSV data
- **Without a CSV file**: Use inline forms to manually add WeightConfigurationItems

See `api/registry/admin.py`.

## DIDKit EIP-712 Signing Requirements

### TypedData Structure Requirement

When signing credentials with EthereumEip712Signature2021 using DIDKit's Rust SSI library, the eip712_domain field in LinkedDataProofOptions must be a properly structured TypedData object from `ssi::ldp::eip712`, not a raw JSON value.

The library expects the domain, types, and primaryType to be in the correct format that matches the TypedData struct definition.

### Credential @context Structure

When creating Passport credentials with EthereumEip712Signature2021 signatures, the nested JSON-LD context object must be placed in `credentialSubject.@context`, NOT in the top-level credential @context array.

**Top-level @context** should only contain URI strings:
```json
{
  "@context": [
    "https://www.w3.org/2018/credentials/v1",
    "https://w3id.org/vc/status-list/2021/v1"
  ]
}
```

**Nested Context in credentialSubject** goes here:
```json
{
  "credentialSubject": {
    "@context": {
      "provider": "https://schema.org/Text",
      "nullifiers": {
        "@type": "https://schema.org/Text",
        "@container": "@list"
      }
    }
  }
}
```

This structure allows DIDKit's EIP-712 TypedData generator to properly parse the credential without "Expected string" errors. See `rust-scorer/comparison-tests/src/gen_credentials.rs`.

## Django Migrations Out of Sync

When Django says "No migrations to apply" but tables don't exist, this usually means the migrations were marked as applied in Django's migration history table but the actual tables were never created. This can happen when:

1. Database was created after migrations were recorded
2. Database was dropped but migration history persisted
3. Multiple database configs got mixed up

**Solution**: Use `migrate --run-syncdb` to force Django to create missing tables, or delete the django_migrations table and run migrations again.

See `dev-setup/setup.sh`.

## PostgreSQL gexec Database Creation

The original setup script used `\gexec` with a SELECT statement to conditionally create the database, but this approach had issues:

1. The script had `\\gexec` (double backslash) which was incorrect syntax
2. Even with correct `\gexec`, this approach can fail silently in some PostgreSQL configurations

**Solution**: Split into two operations:

1. **Check if database exists**:
   ```bash
   psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1
   ```

2. **Create if it doesn't**:
   ```bash
   psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
   ```

This approach is more reliable and provides better error visibility. See `dev-setup/setup.sh`.

## Axum Route Parameter Syntax

Axum 0.8 changed route parameter syntax from colon-based `:param` to brace-based `{param}`. 

**Correct Syntax**:
```rust
.route("/v2/stamps/{scorer_id}/score/{address}", get(score_address_handler))
```

**Incorrect (Old) Syntax**:
```rust
// This causes 'Path segments must not start with :' error
.route("/v2/stamps/:scorer_id/score/:address", get(score_address_handler))
```

The route handler extracts these parameters using `Path((scorer_id, address)): Path<(i32, String)>`. See `rust-scorer/src/api/server.rs`.

## Database Primary Key Types

Many Django tables use BIGINT (i64) for primary keys and foreign keys, not INT4 (i32) as initially assumed. This affects:

- passport_id fields
- score_id fields  
- community_id fields
- account_id fields

All database operations must use the correct i64 type to avoid type mismatches. See `rust-scorer/src/db/write_ops.rs`, `rust-scorer/src/api/handler.rs`.
