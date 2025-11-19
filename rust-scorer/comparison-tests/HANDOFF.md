# Python ↔ Rust Comparison Testing - Handoff Document

## Overview

We're migrating the Passport Scorer from Python (Django) to Rust for performance improvements. Before fully switching traffic, we need to verify that both implementations return identical results for the same inputs.

This comparison test infrastructure automatically starts both servers and verifies their responses match.

## Current Status

### Completed

1. **Test infrastructure** (`rust-scorer/comparison-tests/`)
   - Cargo binary that orchestrates comparison tests
   - Automatic loading of `.env.development` using dotenvy
   - Server management (starts Python on :8002, Rust on :3000)
   - JSON response comparison with sorted keys
   - Pretty diff output on mismatches
   - Loads test config from `test_config.json`
   - Methods for internal API auth (`compare_get_internal`)

2. **First test passing**: `GET /internal/embed/weights`
   - Stateless endpoint, no authentication
   - Both servers return identical weights from database

3. **Dev setup fixes** (`dev-setup/`)
   - Added Redis/Valkey to prerequisites and setup instructions
   - Fixed `.env.development` format (standard .env, no bash syntax)
   - Fixed `create_test_data.py` scorer type (`WEIGHTED_BINARY`)
   - Added `CERAMIC_CACHE_SCORER_ID=1` and `sslmode=disable`
   - Added `python-dotenv` to project dependencies

4. **Test credential generation** (`dev-setup/create_test_credentials.py`)
   - Uses DIDKit to sign credentials with Ed25519 keys
   - Creates 3 stamps: Google (1.0), Twitter (1.0), Github (2.0) = 4.0 total weight
   - Test address: `0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
   - Saves config to `rust-scorer/comparison-tests/test_config.json`
   - Credentials verified as VALID by DIDKit

5. **Environment configuration**
   - Added `TRUSTED_IAM_ISSUERS` with test issuer DID
   - Added `CGRANTS_API_TOKEN=abc` for internal API auth
   - Regenerated SQLX query cache

6. **Scoring endpoint test added** - `GET /internal/score/v2/{scorer_id}/{address}`
   - Uses internal API with Authorization header
   - Shows error response bodies on failure

### In Progress / Remaining Issues

#### Immediate Issues to Debug

1. **Python scoring returns 500**: `"Failed to calculate score."`
   - Credentials are properly signed and verified
   - TRUSTED_IAM_ISSUERS is set in `.env.development`
   - Need to verify Django is actually loading the env var

2. **Rust scoring returns 500**: `"no column found for name: stamp_type"`
   - SQLX query cache was regenerated
   - Query uses `type AS stamp_type` alias
   - May need to check SQLX offline mode or query mapping

### Remaining Work

#### Phase 2: Data Population & Scoring Test (Partially Complete)

1. ~~**Extend test data**~~ - DONE via `create_test_credentials.py`

2. **Debug scoring endpoint** - Both servers return 500 errors
   - Python: Verify TRUSTED_IAM_ISSUERS loading
   - Rust: Fix stamp_type column mapping issue

3. **Add more internal endpoints**:
   - `POST /internal/check-bans`
   - `POST /internal/check-revocations`
   - `GET /internal/stake/gtc/{address}`
   - `GET /internal/allow-list/{list}/{address}`

4. **Add embed endpoints** (if needed):
   - `GET /internal/embed/score/{scorer_id}/{address}`
   - `POST /internal/embed/stamps/{address}`

5. **Human points testing** (optional, lower priority):
   - Requires `HUMAN_POINTS_ENABLED=true`
   - More complex setup with MetaMask OG list, etc.

## Architecture

### File Structure

```
rust-scorer/comparison-tests/
├── Cargo.toml          # Dependencies: tokio, reqwest, serde_json, dotenvy, etc.
├── README.md           # Usage instructions
├── HANDOFF.md          # This document
└── src/
    └── main.rs         # Test runner (~300 lines)
```

### How It Works

1. `load_env_file()` - Loads `.env.development` from project root using dotenvy
2. `ServerManager` - Spawns Python and Rust servers as child processes
3. `wait_for_healthy()` - Polls health endpoints until both respond (60s timeout)
4. `TestRunner::compare_get()` - Makes same request to both, compares JSON responses
5. `TestRunner::compare_get_internal()` - Same but with Authorization header for internal API
6. `compare_json()` - Deep comparison with sorted keys for deterministic matching

### Key Design Decisions

- **60 second timeouts** - Allows time for Rust server to compile and start
- **dotenvy for env loading** - Standard .env format, no shell variable expansion
- **Override existing env vars** - Uses `from_path_override()` to ensure file values win
- **envs inheritance** - Child processes get all parent env vars via `.envs(std::env::vars())`
- **Error response display** - Shows response bodies when both servers return errors

## Running the Tests

### Prerequisites

```bash
# 1. Start PostgreSQL
./dev-setup/start-postgres.sh

# 2. Start Redis/Valkey
valkey-server --daemonize yes --port 6379

# 3. Create base test data (scorers, communities, API keys)
cd api
poetry run python ../dev-setup/create_test_data.py

# 4. Create signed test credentials (stamps with valid signatures)
poetry run python ../dev-setup/create_test_credentials.py
```

**Note**: `create_test_credentials.py` generates a new issuer DID each time. It updates:
- `rust-scorer/comparison-tests/test_config.json` with the API key and test address
- You must update `TRUSTED_IAM_ISSUERS` in `.env.development` with the new DID (printed at end of script)

### Run Comparison Tests

```bash
cd rust-scorer/comparison-tests
cargo run --release
```

Expected output:
```
========================================
  Python <-> Rust Comparison Tests
========================================

Loaded environment from .env.development
Starting Python server...
Starting Rust server...
Waiting for servers to be healthy...
  Python server ready (2s)
  Rust server ready (1s)

Running comparison tests...
--------------------------------------------------
Testing Weights endpoint ... PASS

==================================================
Results: 1 passed, 0 failed
==================================================

Shutting down servers...
```

## Adding New Tests

### Simple GET endpoint

```rust
test_runner
    .compare_get("Endpoint name", "/path/to/endpoint")
    .await?;
```

### With authentication (TODO)

Need to add methods like:
```rust
test_runner
    .compare_get_with_api_key("Score endpoint", "/v2/stamps/1/score/0x...", &api_key)
    .await?;
```

### With POST body (TODO)

```rust
test_runner
    .compare_post("Check bans", "/internal/check-bans", &json_body)
    .await?;
```

## Known Issues & Gotchas

1. **Scorer type** - Django expects `WEIGHTED_BINARY`, not `BinaryWeightedScorer`

2. **CERAMIC_CACHE_SCORER_ID** - Required by Python's weights endpoint, defaults to reading from env

3. **sslmode=disable** - Required for local PostgreSQL; Rust scorer auto-adds `sslmode=require` for production

4. **Redis required** - Python Django uses Redis for caching; Valkey is a drop-in replacement on Fedora

5. **scorer_id vs community_id** - API uses `scorer_id` but database uses `community_id` (1:1 mapping)

## Files Modified in This Session

### New Files
- `dev-setup/create_test_credentials.py` - DIDKit-signed test credential generator
- `rust-scorer/comparison-tests/test_config.json` - Test configuration (API key, address, issuer DID)

### Modified Files
- `rust-scorer/comparison-tests/src/main.rs` - Added internal API auth, test config loading, 60s timeouts
- `rust-scorer/src/domain/weights.rs` - Fixed to read `CERAMIC_CACHE_SCORER_ID` from env
- `dev-setup/DEV_SETUP.md` - Added Redis/Valkey, updated env format
- `dev-setup/create_test_data.py` - Fixed scorer type, uses python-dotenv
- `.env.development` - Added TRUSTED_IAM_ISSUERS, CGRANTS_API_TOKEN
- `api/pyproject.toml` - Added python-dotenv dependency
- `rust-scorer/.sqlx/` - Regenerated query cache

## References

- **Endpoint mapping**: `.claude/knowledge/architecture/api_endpoint_map.md`
- **Scoring flow**: `.claude/knowledge/architecture/scoring_flow.md`
- **Dev setup guide**: `dev-setup/DEV_SETUP.md`
- **Rust scorer**: `rust-scorer/src/`

## Contact

This work was done as part of the Rust migration effort. The comparison tests ensure we can safely route traffic to the Rust implementation with confidence that results match Python exactly.
