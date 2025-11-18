# Internal API Rust Implementation Progress

## Status: 7/7 Endpoints Implemented ✅

Last updated: 2025-11-18

## Completed Endpoints

### 1. Allow-list Check
- **Endpoint**: `GET /internal/allow-list/{list}/{address}`
- **Files**: `src/db/queries/utils.rs`, `src/domain/allow_list.rs`
- **Status**: ✅ Complete with SQLX compile-time verification

### 2. Credential Customization
- **Endpoint**: `GET /internal/customization/credential/{provider_id}`
- **Files**: `src/db/queries/utils.rs`, `src/domain/allow_list.rs`
- **Status**: ✅ Complete with URL decoding support

### 3. Check Bans
- **Endpoint**: `POST /internal/check-bans`
- **Files**: `src/db/queries/bans.rs`, `src/domain/bans.rs`
- **Status**: ✅ Complete
- **Features**:
  - Supports account, hash, and single_stamp ban types
  - Case-insensitive address matching
  - Returns end_time and reason

### 4. Check Revocations
- **Endpoint**: `POST /internal/check-revocations`
- **Files**: `src/db/queries/bans.rs`
- **Status**: ✅ Complete
- **Features**: Batch proof_value checking

### 5. GTC Stakes
- **Endpoint**: `GET /internal/stake/gtc/{address}`
- **Files**: `src/db/queries/stakes.rs`, `src/domain/stakes.rs`
- **Status**: ✅ Complete
- **Features**: Queries stake_stake table for staker/stakee

### 6. Legacy GTC Stakes
- **Endpoint**: `GET /internal/stake/legacy-gtc/{address}/{round_id}`
- **Files**: `src/db/queries/stakes.rs`, `src/domain/stakes.rs`
- **Status**: ✅ Complete
- **Features**: Queries registry_gtcstakeevent table

### 7. CGrants Contributor Statistics
- **Endpoint**: `GET /internal/cgrants/contributor_statistics`
- **Files**: `src/db/queries/cgrants.rs`, `src/domain/cgrants.rs`
- **Status**: ✅ Complete
- **Features**:
  - Combines cgrants and protocol contributions
  - Squelch filtering via cgrants_squelchedaccounts + cgrants_roundmapping
  - Minimum $0.95 threshold for protocol contributions
  - Returns count of distinct grants/projects and total amount (rounded to 2 decimals)

## Recent Fixes

1. **SQLX Query Alignment** - Updated all queries to match fresh Django migration schema
2. **Model Updates** - `DjangoCeramicCache.stamp_type` now uses integer (1=V1, 2=V2)
3. **Dev Setup** - Fixed `ALLOWED_HOSTS` format in `dev-setup/setup.sh` (must be JSON array)
4. **Nullable Fields** - Properly handle nullable columns like `ceramic_cache.address`

## Build Status

```bash
cargo build  # Passes with warnings only
```

All implemented queries are SQLX compile-time verified against the database schema.

## Database Requirements

The dev database must have all Django migrations applied. Run:
```bash
cd api && poetry run python manage.py migrate --database default
```

## Next Steps

1. ~~Implement cgrants contributor statistics (complex query)~~ ✅ Complete
2. Wire up remaining handlers to domain layer where needed
3. Add integration tests for new endpoints
4. Update SQLX prepared queries (`cargo sqlx prepare`)
