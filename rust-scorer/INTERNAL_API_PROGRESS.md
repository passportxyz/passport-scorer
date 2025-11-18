# Rust Scorer - Remaining Tasks

## Status: Nearly Complete

The Rust scorer migration is largely complete. Two internal API handlers need their input processing implemented.

## Remaining Work

### 1. Check Bans Handler

**File**: `src/api/handlers/internal.rs:89-102`
**Endpoint**: `POST /internal/check-bans`

**Current state**: Returns empty array, needs credential processing

**What needs to be done**:
1. Parse the incoming `Vec<serde_json::Value>` credentials
2. Extract address from DID in each credential
3. Extract hashes and providers from credentials
4. Call `domain::bans::check_credentials_for_bans()`
5. Return `Vec<BanCheckResult>`

**Python reference**: `api/internal/api.py` - `check_bans()` function

### 2. Check Revocations Handler

**File**: `src/api/handlers/internal.rs:104-114`
**Endpoint**: `POST /internal/check-revocations`

**Current state**: Returns empty array, needs proof_value extraction

**What needs to be done**:
1. Parse incoming payload with proof_values
2. Query `ceramic_cache_revocation` table
3. Return list of revoked proof_values

**Python reference**: `api/internal/api.py` - `check_revocations()` function

## Database Queries Already Implemented

The underlying database queries exist in `src/db/queries/bans.rs`:
- Ban checking queries are ready
- Just need the handler to extract data from credentials and call them

## Testing

Run all tests with:
```bash
export DATABASE_URL=postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev
cargo test --lib
```

Currently: 61 tests passing
