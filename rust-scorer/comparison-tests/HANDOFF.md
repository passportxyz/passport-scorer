# Python ↔ Rust Comparison Testing - Handoff Document

## Overview

We're migrating the Passport Scorer from Python (Django) to Rust for performance improvements. Before fully switching traffic, we need to verify that both implementations return identical results for the same inputs.

This comparison test infrastructure automatically starts both servers and verifies their responses match.

---

## ✅ BUGS FIXED!

The comparison tests with realistic data caught **2 real bugs** - both now fixed:

### Bug 1: Check Bans Endpoint - Timestamp Formatting Mismatch ✅ FIXED

**Issue**: Rust was including full microseconds, Python only includes milliseconds

```diff
- Python: "end_time": "2025-12-20T13:28:39.584Z"
- Rust:   "end_time": "2025-12-20T13:28:39.584855Z"  (OLD)
+ Rust:   "end_time": "2025-12-20T13:28:39.584Z"     (FIXED)
```

**Location**: `rust-scorer/src/domain/bans.rs:BanCheckResult`

**Fix Applied**: Added custom serializer `serialize_datetime_millis` to format timestamps with milliseconds precision only (%.3f)

### Bug 2: GTC Stake Endpoint - Integer Field Returned as String ✅ FIXED

**Issue**: `last_updated_in_block` should be an integer, not a string

```diff
- Python: "last_updated_in_block": 12345678
- Rust:   "last_updated_in_block": "12345678"  (OLD)
+ Rust:   "last_updated_in_block": 12345678    (FIXED)
```

**Location**: `rust-scorer/src/domain/stakes.rs:StakeSchema`

**Fix Applied**: Changed field type from `String` to `i64` and added conversion from Decimal to i64

---

## 📊 Current Test Status: 8/8 Passing ✅

```
✅ PASS: Weights endpoint
✅ PASS: Internal Score endpoint
✅ PASS: Check Bans endpoint
✅ PASS: Check Revocations endpoint
✅ PASS: GTC Stake endpoint
✅ PASS: Allow List endpoint
✅ PASS: Embed Score endpoint
✅ PASS: Embed Stamps POST endpoint
```

**All 8 endpoints implemented and passing!**

---

## 📋 Priority Tasks

### Task 1: Fix the Two Bugs Above ✅ COMPLETE

- [x] Fix timestamp formatting in Check Bans endpoint
- [x] Fix integer serialization in GTC Stake endpoint
- [x] Run comparison tests to verify: `cd rust-scorer/comparison-tests && cargo run --release`

### Task 2: Add CGrants Test Data

The CGrants endpoint currently returns empty results (no test data).

**What to create**:
- Grant contributions in `cgrants_grantcontributionindex` table
- Protocol contributions in `cgrants_protocolcontributions` table
- Squelched accounts in `cgrants_squelchedaccounts` table
- Round mappings in `cgrants_roundmapping` table

**Note**: Complex FK relationships make this tricky. See incomplete script at `dev-setup/create_comprehensive_test_data.py`.

**Simpler alternative**: Create minimal SQL script that directly inserts rows, bypassing Django ORM constraints.

### Task 3: Add Error Test Cases

Currently only testing happy paths. Need error handling verification:

**Test scenarios**:
- [ ] Invalid Ethereum address (should return 400)
- [ ] Missing API key / Authorization header (should return 401)
- [ ] Non-existent resources (should return 404)
- [ ] Malformed request bodies (should return 400)

**Files to modify**: `rust-scorer/comparison-tests/src/main.rs` - Add error test methods

**Example**:
```rust
test_runner
    .compare_error("Invalid address", "/internal/score/v2/1/not-an-address", 400, &internal_key)
    .await?;
```

### Task 4: Improve Endpoint-Specific Coverage

- [ ] **Check Bans**: Already has realistic data (active/expired bans, single stamp bans)
- [ ] **Check Revocations**: Need ceramic cache entries with revoked proof values
- [ ] **GTC Stake**: ✅ Already has realistic data (1500.75 GTC total)
- [ ] **Allow List**: ✅ Already has realistic data (testlist membership)

---

## 🛠️ Development Workflow

### Running Comparison Tests

```bash
# 1. Ensure test data exists
cd api
poetry run python ../dev-setup/create_test_data.py
poetry run python ../dev-setup/create_simple_test_data.py

# 2. Generate credentials
cd ../rust-scorer/comparison-tests
ulimit -n 4096
cargo run --bin gen-credentials

# 3. Run comparison tests
cargo run --release

# Or with verbose output:
cargo run --release -- --verbose
```

### Test Data Setup

**Base data** (`create_test_data.py`):
- 3 test scorers/communities with weights
- API keys for testing

**Utility endpoint data** (`create_simple_test_data.py`):
- Allow list: `0xaaaa...` in 'testlist'
- Bans: Active ban for `0xbbbb...`, expired ban + single stamp ban for `0xaaaa...`
- GTC Stakes: 1500.75 GTC total for `0xaaaa...`

**Credentials** (`gen-credentials` binary):
- Production-format EthereumEip712Signature2021 credentials
- Hardcoded issuer DID: `did:ethr:0x018d103c154748e8d5a1d7658185125175457f84`
- 3 stamps: Google (1.0), Twitter (1.0), Github (2.0) = 4.0 total weight

---

## ✅ Definition of Done

Comparison tests are complete when:

1. All 8 current tests pass with realistic data
2. CGrants endpoint returns meaningful results (not empty)
3. Error test cases added for common failure scenarios
4. Both bugs identified above are fixed
5. Tests consistently pass on multiple runs

---

## 📚 What's NOT Covered Yet

### Ceramic Cache Endpoints (Not Implemented in Rust)

The following ceramic cache endpoints exist in Python but are **NOT yet implemented** in Rust:
- ❌ `PATCH /ceramic-cache/stamps/bulk` - Update existing stamps
- ❌ `DELETE /ceramic-cache/stamps/bulk` - Delete stamps by provider
- ❌ `GET /ceramic-cache/stamp` - Get stamps for authenticated user

Already implemented in Rust:
- ✅ `POST /ceramic-cache/stamps/bulk` - Add stamps and rescore
- ✅ `GET /ceramic-cache/score/{address}` - Get score with stamps

**Decision needed**: Are these endpoints needed for production migration?

### Human Points Testing (Lower Priority)

More complex setup required - see `.claude/knowledge/api/human_points.md` for details.

---

## 🏗️ Architecture

### How It Works

1. **Port check** - Ensures ports 3000/8002 are free
2. **Environment loading** - Loads `.env.development` using dotenvy
3. **Server management** - Spawns Python (port 8002) and Rust (port 3000) servers
4. **Health polling** - Waits for both servers to be ready (60s Python, 120s Rust)
5. **Request comparison** - Makes identical requests to both servers
6. **Response validation** - Deep JSON comparison with sorted keys
7. **Automatic cleanup** - Kills server processes on exit (even on panic)

### Key Design Decisions

- **Process groups** - Python spawns with `process_group(0)` so we can kill all Django children
- **Stdout draining** - Prevents pipe buffer (64KB) from blocking the server
- **Hardcoded issuer key** - Test issuer DID is constant across runs
- **Ignored fields** - `last_score_timestamp` and `id` stripped before comparison (naturally differ)
- **Array sorting** - Arrays sorted by JSON representation for order-independent comparison

### File Structure

```
rust-scorer/comparison-tests/
├── Cargo.toml               # Dependencies and build config
├── README.md                # Quick start guide
├── HANDOFF.md               # This document
├── test_config.json         # Test configuration (address, credentials)
└── src/
    ├── main.rs              # Test runner (~700 lines)
    └── gen_credentials.rs   # Credential generator binary
```

---

## 🔧 Known Issues & Gotchas

1. **Scorer type** - Django expects `WEIGHTED_BINARY`, not `BinaryWeightedScorer`
2. **CERAMIC_CACHE_SCORER_ID** - Required by Python's weights endpoint
3. **scorer_id vs community_id** - API uses `scorer_id` but database uses `community_id` (1:1 mapping)
4. **Cargo env var inheritance** - Must filter out `CARGO_*` env vars when spawning cargo processes
5. **Pipe buffer blocking** - Must drain stdout to prevent 64KB buffer from filling
6. **Django child processes** - Use process groups to kill all children
7. **Timestamp comparison** - `last_score_timestamp` differs naturally (sequential calls)

---

## 📖 References

- **API endpoint inventory**: `.claude/knowledge/api/internal_api_endpoints.md`
- **Scoring flow**: `.claude/knowledge/architecture/scoring_flow.md`
- **Dev setup guide**: `dev-setup/DEV_SETUP.md`
- **Comparison testing workflow**: `.claude/knowledge/workflows/comparison_testing.md`

---

**Last Updated**: 2025-11-20
**Status**: 8/8 tests passing ✅ (all bugs fixed!)
**Next**: Add CGrants data, add error tests, improve endpoint-specific coverage
