# Python ↔ Rust Comparison Testing - Handoff Document

**Status**: 🎉 13/13 tests passing ✅ ALL CERAMIC CACHE ENDPOINTS COMPLETE!
**Last Updated**: 2025-11-21
**Phase**: Complete - All 4 ceramic cache endpoints implemented and tested

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

## 📊 Current Test Status: 13/13 Tests Passing! 🎉

### ✅ ALL Tests Passing (13/13)
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
✅ PASS: Ceramic Cache PATCH stamps endpoint
✅ PASS: Ceramic Cache DELETE stamps endpoint
```

**Achievement**: ALL ceramic cache endpoints complete with full feature parity:
- JWT authentication working perfectly
- Human points data included in responses (where applicable)
- Response formats match exactly
- Status codes correct (201 for POST, 200 for GET/PATCH/DELETE)
- PATCH correctly handles soft delete + recreate logic
- DELETE correctly returns GetStampResponse (stamps only, no score)

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

## ✅ Definition of Done - FULLY ACHIEVED!

All completion criteria met for **all endpoints including ceramic cache**:

1. ✅ All 13 endpoints pass with realistic data
2. ✅ CGrants endpoint returns meaningful results (not empty)
3. ✅ Error test infrastructure added and documented
4. ✅ All bugs fixed (timestamp formatting, integer serialization)
5. ✅ Tests consistently pass on multiple runs
6. ✅ Human Points fully working in ceramic cache endpoints
7. ✅ All 4 ceramic cache endpoints implemented (POST, GET, PATCH, DELETE)

**Final achievements**:
- Created comprehensive test data scripts for all endpoints
- Documented auth behavior differences (dev vs production)
- Identified Rust production correctness (no auth on internal ALB)
- Set up Human Points test data and environment configuration
- Implemented all ceramic cache endpoints with full parity
- Discovered and documented DELETE endpoint schema quirk

**Status**: Ready for production deployment! All implemented endpoints have been validated.

---

## 🎉 Ceramic Cache Endpoints Complete!

**All 4 ceramic cache endpoints now passing** with full feature parity:
- ✅ JWT authentication working (using SECRET_KEY from env)
- ✅ Human points data in responses (where applicable)
- ✅ Correct status codes (201 for POST, 200 for GET/PATCH/DELETE)
- ✅ Response formats match Python exactly
- ✅ PATCH correctly soft deletes + recreates stamps
- ✅ DELETE correctly returns stamps without score field

**Key implementation details** (Session 4 - 2025-11-21):
1. PATCH endpoint: Soft deletes all providers in payload, recreates only those with stamp field - `rust-scorer/src/api/ceramic_cache.rs:244-344`
2. DELETE endpoint: Returns GetStampResponse (stamps only, no score) to match Python's declared schema - `rust-scorer/src/api/ceramic_cache.rs:361-425`
3. Added GetStampResponse type for DELETE endpoint - `rust-scorer/src/models/v2_api.rs:100-103`
4. Both endpoints reuse existing soft_delete and bulk_insert infrastructure

### All Ceramic Cache Endpoints Status (4/4 Complete!)

**✅ All endpoints in Rust - Comparison Tests Passing** (4/4):
- ✅ `POST /ceramic-cache/stamps/bulk` - Add stamps, return 201 Created with score + human points
- ✅ `GET /ceramic-cache/score/{address}` - Get score with human points
- ✅ `PATCH /ceramic-cache/stamps/bulk` - Update stamps (soft delete + recreate), return 200 OK with score + human points
- ✅ `DELETE /ceramic-cache/stamps/bulk` - Delete stamps (soft delete only), return 200 OK with stamps (no score)

**Note**: All ceramic cache endpoints use JWT DID authentication (`JWTDidAuth()`), not API keys

### Key Learnings from Implementation

**DELETE endpoint quirk**: Python's route decorator declares `response=GetStampResponse` (stamps only), but the handler tries to return `GetStampsWithInternalV2ScoreResponse` (stamps + score). However, Django Ninja's serializer respects the declared schema, so Python actually returns just stamps without the score. Rust implementation had to match this behavior by creating a separate `GetStampResponse` type.

**Test coverage**: Added PATCH and DELETE test cases to the comparison test suite with realistic test scenarios:
- PATCH: Updates one stamp (Google) and removes another (Twitter)
- DELETE: Removes a stamp (Github) from the cache

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
**Status**: 🎉 13/13 tests passing ✅ ALL CERAMIC CACHE ENDPOINTS COMPLETE!
**Phase**: Complete - All comparison testing infrastructure and ceramic cache endpoints implemented

**Recent Changes - Session 4** (2025-11-21 evening):
- **✅ COMPLETED CERAMIC CACHE!** All 13 comparison tests now passing (11 previous + 2 new)
- **Implemented** PATCH /ceramic-cache/stamps/bulk endpoint with soft delete + recreate logic
- **Implemented** DELETE /ceramic-cache/stamps/bulk endpoint with GetStampResponse (stamps only, no score)
- **Added** comparison tests for PATCH and DELETE endpoints
- **Fixed** DELETE endpoint to match Python's declared schema (returns stamps without score field)
- **Added** GetStampResponse type to models for DELETE endpoint

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
