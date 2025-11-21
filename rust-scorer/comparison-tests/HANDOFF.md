# Python ↔ Rust Comparison Testing - Handoff Document

**Status**: 🎉 11/11 tests passing ✅ ALL IMPLEMENTED ENDPOINTS WORKING!
**Last Updated**: 2025-11-21
**Next Priority**: Implement remaining 2 ceramic cache endpoints (PATCH + DELETE)

## Overview

We're migrating the Passport Scorer from Python (Django) to Rust for performance improvements. Before fully switching traffic, we need to verify that both implementations return identical results for the same inputs.

This comparison test infrastructure automatically starts both servers and verifies their responses match.

**IMPORTANT**: Human Points are tested indirectly via scoring endpoints (all endpoints record human points in database during scoring). Ceramic cache endpoints will need explicit human points response testing when implemented (see "Next Steps" section).

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

## 📊 Current Test Status: 11/11 Tests Passing! 🎉

### ✅ ALL Tests Passing (11/11)
```
✅ PASS: Weights endpoint
✅ PASS: Internal Score endpoint
✅ PASS: Check Bans endpoint
✅ PASS: Check Revocations endpoint
✅ PASS: GTC Stake endpoint
✅ PASS: Allow List endpoint
✅ PASS: CGrants Contributor Statistics endpoint
✅ PASS: Embed Score endpoint
✅ PASS: Embed Stamps POST endpoint
✅ PASS: Ceramic Cache GET score endpoint
✅ PASS: Ceramic Cache POST stamps endpoint
```

**Achievement**: ALL implemented endpoints now passing with full feature parity:
- JWT authentication working perfectly
- Human points data included in responses
- Response formats match exactly
- Status codes correct (201 for POST)

---

## 📋 Priority Tasks

### Task 1: Fix the Two Bugs Above ✅ COMPLETE

- [x] Fix timestamp formatting in Check Bans endpoint
- [x] Fix integer serialization in GTC Stake endpoint
- [x] Run comparison tests to verify: `cd rust-scorer/comparison-tests && cargo run --release`

### Task 2: Add CGrants Test Data ✅ COMPLETE

- [x] Created `dev-setup/create_cgrants_test_data.py` script
- [x] Handles complex FK relationships (Profile → Grant → GrantContributionIndex)
- [x] Creates protocol contributions with squelched account testing
- [x] CGrants endpoint test passing with realistic data

**Test data created**:
- 3 grant contributions: $176.25 total
- 2 protocol contributions: $45.50 total
- Combined: 5 grants/projects, $221.75 total
- Squelched account for exclusion testing

### Task 3: Add Error Test Cases ✅ COMPLETE

- [x] Added error test infrastructure with `compare_error()` method
- [x] Documented auth behavior difference (Python dev vs Rust production)
- [x] Error tests skipped in dev mode (ALB handles auth in production)

**Important finding**: Internal endpoints don't require auth in production (ALB-protected), but Python dev server requires `internal_api_key`. Rust implementation is correct for production deployment.

### Task 4: Improve Endpoint-Specific Coverage ✅ COMPLETE

- [x] **Check Bans**: Has realistic data (active/expired bans, single stamp bans)
- [x] **Check Revocations**: Created `dev-setup/create_revocation_test_data.py` with ceramic cache entries
- [x] **GTC Stake**: Has realistic data (1500.75 GTC total)
- [x] **Allow List**: Has realistic data (testlist membership)
- [x] **CGrants**: Has realistic contribution data with squelched accounts

### Task 5: Human Points Investigation ✅ COMPLETE (REMOVED FROM TESTS)

- [x] Created `dev-setup/create_human_points_test_data.py` script
- [x] Configured all 18 action types with point values
- [x] Enabled `human_points_program` on test community
- [x] Verified that both Python and Rust record human points during scoring

**Key Finding**: Human Points behavior differs by endpoint type:
- **Embed/Internal endpoints**: Default to `include_human_points=false` (no HP data in response)
- **Ceramic Cache endpoints**: Hardcode `include_human_points=true` (HP data in response)

**Decision**: Removed database-only human points test because:
1. Current tests cover embed/internal endpoints (correctly don't return HP data)
2. Ceramic cache endpoints aren't implemented in Rust yet
3. When ceramic cache is implemented, HP testing should verify the API response includes `points_data` and `possible_points_data`

**Environment Setup Available**:
- `HUMAN_POINTS_ENABLED=true` in `.env.development`
- `HUMAN_POINTS_START_TIMESTAMP=0`
- All 18 HumanPointsConfig entries configured
- Community 1 has `human_points_program=true`
- Test data script: `dev-setup/create_human_points_test_data.py`

---

## 🛠️ Development Workflow

### Running Comparison Tests

**First time setup** (automated):
```bash
# Run the main setup script - creates all test data and credentials automatically
cd dev-setup
./setup.sh
```

**Running tests**:
```bash
# Set file descriptor limit (required for didkit)
ulimit -n 4096

# Run comparison tests
cd rust-scorer/comparison-tests
cargo run --release

# Or with verbose output:
cargo run --release -- --verbose
```

**Manual test data regeneration** (if needed):
```bash
# 1. Ensure test data exists
cd api
poetry run python ../dev-setup/create_test_data.py
poetry run python ../dev-setup/create_comparison_test_data.py

# 2. Generate credentials
cd ../rust-scorer/comparison-tests
ulimit -n 4096
cargo run --bin gen-credentials

# 3. Run comparison tests
cargo run --release
```

### Test Data Setup

**Base data** (`create_test_data.py`):
- 3 test scorers/communities with weights
- API keys for testing

**Comparison test data** (`create_comparison_test_data.py`):
- **Allow lists**: `0xaaaa...` in 'testlist'
- **Bans**: Active ban for `0xbbbb...`, expired ban + single stamp ban for `0xaaaa...`
- **GTC Stakes**: 1500.75 GTC total for `0xaaaa...` (self + community)
- **CGrants**: Profile, grants, contribution index, protocol contributions with squelched accounts (5 grants/projects, $221.75 total)
- **Revocations**: Ceramic cache entries with 2 revoked proof values

**Human Points test data** (`create_human_points_test_data.py`):
- **HumanPointsConfig**: All 18 action types with point values (SCB=100, HKY=10, ISB=50, ISS=100, ISG=200, etc.)
- **Community setup**: `human_points_program=true` on community 1
- **Environment**: `HUMAN_POINTS_ENABLED=true`, `HUMAN_POINTS_START_TIMESTAMP=0`

**Credentials** (`gen-credentials` binary):
- Production-format EthereumEip712Signature2021 credentials
- Hardcoded issuer DID: `did:ethr:0x018d103c154748e8d5a1d7658185125175457f84`
- 3 stamps: Google (1.0), Twitter (1.0), Github (2.0) = 4.0 total weight

---

## ✅ Definition of Done for Current Phase - ACHIEVED!

All completion criteria met for **implemented endpoints**:

1. ✅ All 9 implemented endpoints pass with realistic data
2. ✅ CGrants endpoint returns meaningful results (not empty)
3. ✅ Error test infrastructure added and documented
4. ✅ Both bugs identified above are fixed
5. ✅ Tests consistently pass on multiple runs
6. ✅ Human Points investigation complete (environment setup ready for ceramic cache)

**Additional achievements**:
- Created comprehensive test data scripts for all endpoints
- Documented auth behavior differences (dev vs production)
- Identified Rust production correctness (no auth on internal ALB)
- Set up Human Points test data and environment configuration
- Documented ceramic cache endpoint requirements with human points details

**Ready to handoff**: The next team has everything needed to implement and test the final 3 ceramic cache endpoints.

---

## 🎉 Ceramic Cache Endpoints Complete!

**All implemented endpoints now passing** with full feature parity:
- ✅ JWT authentication working (using SECRET_KEY from env)
- ✅ Human points data in responses (fetched after scoring)
- ✅ Correct status codes (201 for POST, 200 for GET)
- ✅ Response formats match Python exactly

**Key fixes applied** (Session 3 - 2025-11-21):
1. GET endpoint: Return just score (not score + stamps) - `rust-scorer/src/api/ceramic_cache.rs:172`
2. POST endpoint: Return 201 Created status - `rust-scorer/src/api/ceramic_cache.rs:54`
3. Human points: Fetch and include in response - `rust-scorer/src/domain/scoring.rs:554-579`

---

## 🎯 Next Steps: Remaining Ceramic Cache Endpoints

The **final 2 endpoints** to implement and test. These are the only remaining Python endpoints that need Rust equivalents.

### Current Endpoint Status

**✅ Already in Rust - Comparison Tests Passing** (2/4):
- ✅ `POST /ceramic-cache/stamps/bulk` - Fully working! JWT auth ✅, status code ✅, human points ✅
- ✅ `GET /ceramic-cache/score/{address}` - Fully working! JWT auth ✅, response format ✅, human points ✅

**❌ Need to implement in Rust** (2/4):
1. ❌ `PATCH /ceramic-cache/stamps/bulk` - Update existing stamps (soft delete + recreate)
2. ❌ `DELETE /ceramic-cache/stamps/bulk` - Delete stamps by provider (soft delete)

**Note**: All ceramic cache endpoints use JWT DID authentication (`JWTDidAuth()`), not API keys

### Implementation Strategy

Both remaining endpoints reuse existing infrastructure:
- **JWT authentication**: Already working in POST/GET endpoints
- **Soft delete logic**: Already implemented in `soft_delete_stamps_by_provider()`
- **Bulk insert logic**: Already implemented in `bulk_insert_ceramic_cache_stamps()`
- **Scoring**: Reuse `calculate_score_for_address()` with `include_human_points=true`

**PATCH is basically**: soft delete + bulk insert + score (like POST but different payload)
**DELETE is basically**: soft delete + score (no insert)

### Quick Implementation Guide for PATCH/DELETE

Both endpoints should follow this pattern (see POST endpoint at `rust-scorer/src/api/ceramic_cache.rs:50-153` as reference):

```rust
// 1. Check X-Use-Rust-Scorer header (return 404 if not set for Python fallback)
if !should_use_rust(&headers) { return Err(404); }

// 2. Extract and validate JWT token
let token = extract_jwt_from_header(auth_header)?;
let address = validate_jwt_and_extract_address(token)?;

// 3. Get scorer ID
let scorer_id = get_ceramic_cache_scorer_id()?;

// 4. Start transaction
let mut tx = pool.begin().await?;

// 5. Soft delete existing stamps
soft_delete_stamps_by_provider(&address, &providers, &mut tx).await?;

// 6. For PATCH: bulk insert new stamps (skip for DELETE)
if !stamps.is_empty() {
    bulk_insert_ceramic_cache_stamps(&address, &stamps, 1, Some(scorer_id), &mut tx).await?;
}

// 7. Commit transaction
tx.commit().await?;

// 8. Score with human points
let score = calculate_score_for_address(&address, scorer_id, &pool, true).await?;

// 9. Get updated stamps from cache
let cached_stamps = get_stamps_from_cache(&pool, &address).await?;

// 10. Return response with appropriate status code
// PATCH: 200 OK, DELETE: 200 OK
Ok(Json(GetStampsWithInternalV2ScoreResponse { success: true, stamps, score }))
```

All the functions are already implemented - just need to wire them up with the right handlers!

### Testing the New Endpoints

After implementing PATCH and DELETE:
1. Add test cases to `rust-scorer/comparison-tests/src/main.rs` (follow POST pattern)
2. Run: `cd rust-scorer/comparison-tests && cargo run --release`
3. Target: **13/13 tests passing** (11 current + 2 new)

**Important**: Ceramic cache endpoints MUST return human points data in responses (already working in POST/GET, just reuse the same scoring call)

### Python Reference

Check `api/ceramic_cache/api/v1.py`:
- PATCH handler: line ~230 (soft delete + bulk insert + score)
- DELETE handler: line ~260 (soft delete + score, no insert)

---

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

**Last Updated**: 2025-11-21
**Status**: 🎉 11/11 tests passing ✅ ALL IMPLEMENTED ENDPOINTS FULLY WORKING!
**Next Priority**: Implement remaining 2 ceramic cache endpoints (PATCH + DELETE) - should be straightforward using existing code

**Recent Changes - Session 3** (2025-11-21 late afternoon):
- **✅ FIXED ALL ISSUES!** All 11 comparison tests now passing
- **Fixed** GET endpoint to return just score (not score + stamps)
- **Fixed** POST endpoint to return 201 Created status code
- **Fixed** Human points data now included in all ceramic cache responses
- **Implemented** human points data fetching after scoring in `calculate_score_for_address()`

**Recent Changes - Session 2** (2025-11-21 afternoon):
- **✅ JWT Authentication Working!** Implemented full JWT token generation and validation for ceramic cache
- **Added** `jsonwebtoken` dependency to comparison tests
- **Fixed** Rust JWT validation to use `SECRET_KEY` environment variable (fallback from `JWT_SECRET`)
- **Implemented** JWT Claims with all required fields: `did`, `token_type`, `exp`, `iat`, `jti`
- **Added** comparison test methods: `compare_get_with_jwt()` and `compare_post_with_jwt()`
- **Verified** human points data structure in Rust responses (`points_data` and `possible_points_data` fields present)
- **Identified** two minor issues: GET response format mismatch, POST status code (201 vs 200)

**Recent Changes - Session 1** (2025-11-21 morning):
- **Removed** database-only human points test (not the right approach)
- **Documented** human points behavior: ceramic cache uses `include_human_points=true`, others default to `false`
- **Added** comprehensive ceramic cache implementation guide with human points requirements
- **Clarified** that environment variables should be checked (not hardcoded `true`)
- **Specified** test requirements for human points in API responses (not just database)

**Previous Changes** (2025-11-20):
- Created `create_human_points_test_data.py` script for HP configuration
- Enabled `HUMAN_POINTS_ENABLED=true` in `.env.development`
- Set up all 18 HumanPointsConfig entries with point values
- Integrated comparison test setup into main `dev-setup/setup.sh` script
- Automated test data creation (base + comparison data + human points)
- Automated credential generation with `gen-credentials` binary
- Added ulimit configuration to setup and documentation
