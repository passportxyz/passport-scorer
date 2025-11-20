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

### Phase 3 Complete - All Core Endpoints Verified ✅

All comparison tests now pass, including the Embed Stamps POST endpoint using production-format EthereumEip712Signature2021 credentials.

### Previously Completed Issues

#### Completed (Current Session - 2025-11-20)

8. **Embed Stamps POST endpoint enabled** - DONE
   - Uncommented and enabled the POST /internal/embed/stamps/{address} test
   - Test now passes using production-format EthereumEip712Signature2021 credentials
   - All 8 comparison tests passing
   - Updated documentation (DEV_SETUP.md, HANDOFF.md)
   - Added default-run to Cargo.toml for easier test execution

9. **Hardcoded test issuer key** - DONE
   - Fixed gen_credentials.rs to use hardcoded Ethereum key instead of random generation
   - Issuer DID now constant: did:ethr:0x018d103c154748e8d5a1d7658185125175457f84
   - Updated .env.development with the hardcoded DID in TRUSTED_IAM_ISSUERS
   - No longer need to update environment variables after regenerating credentials

#### Completed (Previous Session - Embed Stamps POST)

1. **Python scoring fixed** - DONE
   - Root cause: `create_test_credentials.py` was storing credentials in wrong format
   - Fix: Store just the credential in `CeramicCache.stamp`, not a wrapper dict
   - Python now returns score 4.0 correctly

2. **Rust stamp_type column mapping fixed** - DONE
   - Root cause: `DjangoCeramicCache` struct had 8 fields but query selected 15 columns
   - Fix: Updated queries in `db/queries/stamps.rs` to use `type AS "stamp_type: _"` and select only 8 columns
   - Updated `domain/stamps.rs` and `domain/scoring.rs` to use new query functions

3. **TRUSTED_IAM_ISSUERS loading fixed** - DONE
   - Root cause: Was working correctly via dotenvy all along
   - The issue was zombie server processes (from previous test runs) responding with old binaries
   - Lesson: Always kill old servers before testing (`pkill -f passport-scorer`)

4. **Timestamp formatting fixed** - DONE
   - Root cause: Rust was including `.000000` microseconds when Python omits them for zero values
   - Fix: Updated `format_datetime_python()` in `models/v2_api.rs` to only include microseconds when non-zero
   - Both Python and Rust now return `"2026-02-17T15:37:57+00:00"` format

#### Both comparison tests now pass
- Weights endpoint: PASS
- Internal Score endpoint: PASS (score 4.0, all timestamps match)

5. **Test runner reliability improvements** - DONE
   - **Port availability check** - Fails fast with clear error if ports 3000/8002 are in use
   - **Stdout pipe draining** - Fixed pipe buffer blocking that caused timeouts on verbose endpoints
   - **Timestamp field ignoring** - `last_score_timestamp` naturally differs between sequential calls
   - **Rust error display** - Show errors in red instead of silently dropping them
   - **Process group cleanup** - Uses `libc::kill(-pid)` to kill Django's child process tree
   - **Drop trait cleanup** - Automatic server cleanup even on error/panic (like finally block)

### Remaining Work

#### Completed (Latest Session)

7. **EthereumEip712Signature2021 Credential Generator** - DONE
   - Created Rust binary at `rust-scorer/comparison-tests/src/gen_credentials.rs`
   - Generates production-format credentials matching Passport's TypeScript implementation
   - Key discovery: Nested `@context` belongs in `credentialSubject.@context`, not top-level credential
   - Uses proper EIP-712 typed data structure from `signingDocuments.ts`
   - Generates secp256k1 Ethereum keys (`did:ethr:0x...`)
   - All credentials verified as VALID
   - Saves to `ceramic_cache_ceramiccache` table with proper field values

#### Completed (Previous Session)

6. **Migrated read_ops.rs and write_ops.rs to organized query modules** - DONE
   - Created `db/queries/dedup.rs` for LIFO deduplication queries
   - Added stamp write operations to `db/queries/stamps.rs`
   - Added `load_scorer_config` to `db/queries/weights.rs`
   - Added `load_community` and `upsert_score` to `db/queries/scoring.rs`
   - Updated all domain imports to use new query paths
   - Deleted `read_ops.rs`, `write_ops.rs`, and backup files
   - Build passes, both comparison tests pass

#### Phase 2: Additional Endpoints - COMPLETED

1. ~~**Extend test data**~~ - DONE via `create_test_credentials.py`

2. ~~**Debug scoring endpoint**~~ - DONE, both tests pass

3. ~~**Add more internal endpoints**~~ - DONE
   - `POST /internal/check-bans` - PASS
   - `POST /internal/check-revocations` - PASS
   - `GET /internal/stake/gtc/{address}` - PASS
   - `GET /internal/allow-list/{list}/{address}` - PASS

#### All 8 Comparison Tests Now Pass:
- Weights endpoint
- Internal Score endpoint
- Check Bans endpoint
- Check Revocations endpoint
- GTC Stake endpoint
- Allow List endpoint
- Embed Score endpoint (GET)
- Embed Stamps POST endpoint

#### Production Credential Format - COMPLETE:
- **EthereumEip712Signature2021 credentials** generated using Rust (`cargo run --bin gen-credentials`)
- Uses `did:ethr:0x...` DIDs with secp256k1 keys (production format)
- All credentials verified as VALID by DIDKit
- POST /internal/embed/stamps/{address} endpoint now PASSING

### Next Steps for Incoming Team

#### Phase 4: Human Points Testing (Lower Priority)

More complex setup required:

1. **Environment setup**:
   - Set `HUMAN_POINTS_ENABLED=true` in `.env.development`
   - Set `HUMAN_POINTS_START_TIMESTAMP` to a past date
   - Optionally set `HUMAN_POINTS_MTA_ENABLED=true` for MetaMask OG

2. **Database setup**:
   - Create `registry_humanpointsconfig` entries for point values
   - Optionally populate `account_addresslist` and `account_addresslistmember` for MetaMask OG testing

3. **Test the scoring endpoint with `include_human_points=true`**:
   - The internal score endpoint needs a query parameter variant
   - Response will include `points_data` and `possible_points_data`

4. **Considerations**:
   - Human points change based on number of communities passed (scoring bonus at 4+)
   - MetaMask OG has a 5000 award limit
   - Points calculation involves multipliers and action-specific values

Reference files:
- `api/registry/human_points_utils.py` - Python implementation
- `rust-scorer/src/human_points/` - Rust implementation
- `.claude/knowledge/api/human_points.md` - Documentation

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

1. `ensure_ports_available()` - Checks ports 3000/8002 are free, fails fast with instructions if not
2. `load_env_file()` - Loads `.env.development` from project root using dotenvy
3. `ServerManager` - Spawns Python (with process group) and Rust servers as child processes
4. `wait_for_healthy()` - Polls health endpoints until both respond (60s Python, 120s Rust)
5. `TestRunner::compare_get()` - Makes same request to both, compares JSON responses
6. `TestRunner::compare_get_internal()` - Same but with Authorization header for internal API
7. `compare_json()` - Deep comparison with sorted keys, ignoring timestamp fields that naturally differ
8. `Drop` on `ServerManager` - Automatic cleanup kills process groups even on error/panic

### Key Design Decisions

- **Port pre-check** - Checks ports are free before starting, fails fast with clear error and fix instructions
- **60/120 second timeouts** - Allows time for servers to compile and start (120s for Rust with DIDKit)
- **dotenvy for env loading** - Standard .env format, no shell variable expansion
- **Override existing env vars** - Uses `from_path_override()` to ensure file values win
- **Filtered env inheritance** - Child cargo processes get env vars with `CARGO_*`, `RUSTFLAGS`, etc. filtered out to prevent fingerprint mismatches and unnecessary rebuilds
- **Stdout draining** - Must read stdout from Rust server to prevent pipe buffer (64KB) from filling and blocking the server
- **Process groups** - Python spawns with `process_group(0)` so we can kill all Django children with `kill(-pid)`
- **Drop cleanup** - ServerManager implements Drop to auto-kill servers even on error/panic
- **Error response display** - Shows response bodies when both servers return errors
- **Workspace setup** - comparison-tests is a workspace member of rust-scorer to share target directory and avoid duplicate builds
- **Hardcoded issuer key** - Test issuer Ed25519 key is hardcoded so TRUSTED_IAM_ISSUERS doesn't change between runs
- **Ignored fields** - `last_score_timestamp` and `id` fields are stripped before comparison (auto-increment IDs and timestamps differ naturally)
- **Array sorting** - Arrays are sorted by JSON representation for order-independent comparison

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

# 4. Generate production-format credentials (EthereumEip712Signature2021)
cd ../rust-scorer/comparison-tests
ulimit -n 4096  # DIDKit requires many file descriptors
cargo run --bin gen-credentials
```

**Note**: The credential generator uses a hardcoded test Ethereum key (did:ethr:0x018d103c154748e8d5a1d7658185125175457f84), so the issuer DID remains constant across runs. This DID is already configured in `.env.development` under `TRUSTED_IAM_ISSUERS`.

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

Ports 3000 and 8002 are available
Loaded environment from .env.development
Loaded test config: address=0xaaaaaaaa, scorer_id=1
Starting Python server...
Starting Rust server...
Waiting for servers to be healthy...
  Python server ready (2s)
  Rust server ready (0s)

Running comparison tests...
--------------------------------------------------
Testing Weights endpoint ... PASS
Testing Internal Score endpoint ... PASS
Testing Check Bans endpoint ... PASS
Testing Check Revocations endpoint ... PASS
Testing GTC Stake endpoint ... PASS
Testing Allow List endpoint ... PASS
Testing Embed Score endpoint ... PASS
Testing Embed Stamps POST endpoint ... PASS

==================================================
Results: 8 passed, 0 failed
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

### With POST body (internal API)

```rust
let body = json!({
    "proof_values": ["proof1", "proof2"]
});
test_runner
    .compare_post_internal("Check revocations", "/internal/check-revocations", &body, &internal_key)
    .await?;
```

## Known Issues & Gotchas

1. **Scorer type** - Django expects `WEIGHTED_BINARY`, not `BinaryWeightedScorer`

2. **CERAMIC_CACHE_SCORER_ID** - Required by Python's weights endpoint, defaults to reading from env

3. **sslmode=disable** - Required for local PostgreSQL; Rust scorer auto-adds `sslmode=require` for production

4. **Redis required** - Python Django uses Redis for caching; Valkey is a drop-in replacement on Fedora

5. **scorer_id vs community_id** - API uses `scorer_id` but database uses `community_id` (1:1 mapping)

6. **Cargo env var inheritance** - When spawning cargo as a child process, you must filter out `CARGO_*` env vars. Cargo sets these during builds and they get inherited by the running binary. If passed to a child cargo process, they cause fingerprint mismatches and unnecessary rebuilds. This is a known Rust ecosystem gotcha.

7. **Pipe buffer blocking** - When spawning a process with piped stdout, you MUST continuously read from the pipe. The pipe buffer is ~64KB on Linux. If it fills up, the child process blocks on write() and hangs. This caused sporadic timeouts on verbose endpoints (like internal score) that produce lots of JSON logs.

8. **Django child processes** - `manage.py runserver` spawns multiple processes (reloader + worker). Simply killing the parent doesn't kill children. Must use process groups: spawn with `process_group(0)` and kill with `kill(-pid, SIGKILL)`.

9. **Timestamp comparison** - `last_score_timestamp` will always differ between Python and Rust since they're called sequentially. The test runner strips these fields before comparison.

## Files Modified/Created

### Latest Session
- `rust-scorer/comparison-tests/src/gen_credentials.rs` - NEW: Rust credential generator with EthereumEip712Signature2021
- `rust-scorer/comparison-tests/Cargo.toml` - Added gen-credentials binary and dependencies (didkit, k256, sqlx)
- `rust-scorer/comparison-tests/test_config.json` - Updated with new Ethereum DID and production credentials
- `rust-scorer/comparison-tests/HANDOFF.md` - Updated with progress

### Previous Sessions
- `dev-setup/create_test_credentials.py` - Python Ed25519 credential generator (legacy)
- `rust-scorer/comparison-tests/src/main.rs` - Test runner with internal API auth
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
