# Rust vs Python Endpoint Comparison Report

## Executive Summary

The Rust scorer implementation includes comprehensive endpoint coverage for the Passport scoring system, with both external (API key authenticated) and internal (private ALB) endpoints. The implementation has been designed for direct compatibility testing against the Python endpoints.

---

## 1. ENDPOINT COMPARISON MATRIX

### External V2 API Endpoints (Public - Require API Key)

| Endpoint | Python Path | Rust Path | Python Handler | Rust Handler | Status | Auth |
|----------|-----------|-----------|-----------------|--------------|--------|------|
| Score | `GET /v2/stamps/{scorer_id}/score/{address}` | `GET /v2/stamps/{scorer_id}/score/{address}` | `a_submit_passport()` in `api_stamps.py:173` | `score_address_handler()` in `handlers/external.rs:32` | ✅ COMPLETE | API Key |

**Response Format**: Both return `V2ScoreResponse` with:
- address, score (decimal), passing_score (boolean)
- threshold (decimal), last_score_timestamp, expiration_timestamp
- stamps (dict), error, points_data (if include_human_points=true)

**Query Parameters**: 
- `include_human_points=true` (optional) - enables human points calculation

---

### Internal Embed Lambda Endpoints (Private ALB - No Auth)

| Endpoint | Python | Rust | Python Handler | Rust Handler | Status | Notes |
|----------|--------|------|-----------------|--------------|--------|-------|
| Get Score | `GET /internal/embed/score/{scorer_id}/{address}` | `GET /internal/embed/score/{scorer_id}/{address}` | `handle_get_score()` in `embed/api.py:90` | `get_embed_score_handler()` in `embed.rs:161` | ✅ COMPLETE | Returns stamps + score |
| Add Stamps | `POST /internal/embed/stamps/{address}` | `POST /internal/embed/stamps/{address}` | `handle_embed_add_stamps()` in `embed/api.py:44` | `add_stamps_handler()` in `embed.rs:73` | ✅ COMPLETE | Rescores after adding |
| Validate Key | `GET /internal/embed/validate-api-key` | `GET /internal/embed/validate-api-key` | `handle_validate_embed_api_key()` in `embed/api.py:82` | `validate_api_key_handler()` in `embed.rs:29` | ✅ COMPLETE | Returns embed_rate_limit |

**Response Format for Embed Endpoints**:
- Get Score & Add Stamps: `GetStampsWithV2ScoreResponse` (success flag + stamps + score)
- Validate Key: `AccountAPIKeySchema` (embed_rate_limit field)

---

### Internal API Endpoints (Private ALB - No Auth)

| Endpoint | Python | Rust | Python Handler | Rust Handler | Status |
|----------|--------|------|-----------------|--------------|--------|
| Score V2 | `GET /internal/score/v2/{scorer_id}/{address}` | `GET /internal/score/v2/{scorer_id}/{address}` | `get_score_v2()` in `internal/api.py:108` | `internal_score_handler()` in `handlers/internal.rs:64` | ✅ COMPLETE |
| Weights | `GET /internal/embed/weights` | `GET /internal/embed/weights` | `handle_get_scorer_weights()` in `ceramic_cache/api/v1.py` | `internal_weights_handler()` in `handlers/internal.rs:98` | ✅ COMPLETE |
| Check Bans | `POST /internal/check-bans` | `POST /internal/check-bans` | `handle_check_bans()` in `internal/bans_revocations.py` | `internal_check_bans_handler()` in `handlers/internal.rs:188` | ✅ COMPLETE |
| Check Revocations | `POST /internal/check-revocations` | `POST /internal/check-revocations` | `handle_check_revocations()` in `internal/bans_revocations.py` | `internal_check_revocations_handler()` in `handlers/internal.rs:190` | ✅ COMPLETE |
| Allow List | `GET /internal/allow-list/{list}/{address}` | `GET /internal/allow-list/{list}/{address}` | `handle_check_allow_list()` in `account/api.py` | `internal_allow_list_handler()` in `handlers/internal.rs:202` | ✅ IMPLEMENTED |
| Credential Def | `GET /internal/customization/credential/{provider_id}` | `GET /internal/customization/credential/{provider_id}` | `handle_get_credential_definition()` in `account/api.py` | `internal_credential_definition_handler()` in `handlers/internal.rs:206` | ✅ IMPLEMENTED |
| GTC Stake | `GET /internal/stake/gtc/{address}` | `GET /internal/stake/gtc/{address}` | `handle_get_gtc_stake()` in `stake/api.py` | `internal_stake_gtc_handler()` in `handlers/internal.rs:210` | ✅ IMPLEMENTED |
| Legacy GTC | `GET /internal/stake/legacy-gtc/{address}/{round_id}` | `GET /internal/stake/legacy-gtc/{address}/{round_id}` | `handle_get_gtc_stake_legacy()` in `registry/api/v1.py` | `internal_legacy_stake_handler()` in `handlers/internal.rs:214` | ✅ IMPLEMENTED |
| CGrants Stats | `GET /internal/cgrants/contributor_statistics` | `GET /internal/cgrants/contributor_statistics` | `handle_get_contributor_statistics()` in `cgrants/api.py` | `internal_cgrants_statistics_handler()` in `handlers/internal.rs:218` | ✅ IMPLEMENTED |

---

### Ceramic Cache Endpoints (Public - JWT Auth)

| Endpoint | Python | Rust | Python Handler | Rust Handler | Status | Auth |
|----------|--------|------|-----------------|--------------|--------|------|
| Add Stamps | `POST /ceramic-cache/stamps/bulk` | `POST /ceramic-cache/stamps/bulk` | Django endpoint | `ceramic_cache_add_stamps()` in `ceramic_cache.rs:1` | ✅ COMPLETE | JWT (HS256) |
| Get Score | `GET /ceramic-cache/score/{address}` | `GET /ceramic-cache/score/{address}` | `get_detailed_score_response_for_address()` | `ceramic_cache_get_score()` in `ceramic_cache.rs` | ✅ COMPLETE | JWT (HS256) |

**Authentication**: JWT tokens with HS256 algorithm, address extracted from DID claim format `did:pkh:eip155:1:0xADDRESS`

---

## 2. REQUEST/RESPONSE FORMAT DIFFERENCES

### V2 Score Endpoint
```json
// REQUEST
GET /v2/stamps/{scorer_id}/score/{address}?include_human_points=true
X-API-Key: <api_key>

// RESPONSE (Python & Rust Identical)
{
  "address": "0x1234...",
  "score": "25.34000",          // 5 decimal places
  "passingScore": true,
  "threshold": "20.00000",
  "lastScoreTimestamp": "2025-01-15T10:30:00Z",
  "expirationTimestamp": "2025-04-15T10:30:00Z",
  "error": null,
  "stamps": {
    "google": {
      "score": "10.00000",
      "dedup": false,
      "expiration": "2025-04-15T10:30:00Z"
    }
  },
  "pointsData": {                // Only if include_human_points=true
    "totalPoints": 120,
    "isEligible": true,
    "multiplier": 1.5,
    "breakdown": { "HKY": 10 }
  }
}
```

### Embed Add Stamps
```json
// REQUEST
POST /internal/embed/stamps/{address}
{
  "scorer_id": 1,               // Can be string or number
  "stamps": [
    {
      "credentialSubject": {
        "provider": "google",
        "nullifiers": ["null1"]
      },
      "proof": {...}
    }
  ]
}

// RESPONSE (Both Python & Rust)
{
  "success": true,
  "stamps": [...],              // Full stamp objects from ceramic_cache
  "score": { ...V2ScoreResponse... }
}
```

### Internal Weights Endpoint
```json
// RESPONSE (No Auth - Python & Rust)
{
  "google": 25.5,
  "twitter": 15.3,
  "github": 10.0,
  // ... more providers
}
```

### Check Bans Endpoint
```json
// REQUEST
POST /internal/check-bans
[
  {
    "credential_subject": {
      "hash": "abc123...",
      "provider": "google",
      "id": "did:..."
    }
  }
]

// RESPONSE (Python & Rust Identical)
[
  {
    "hash": "abc123...",
    "banned": true,
    "end_time": "2025-12-31T23:59:59Z"
  }
]
```

---

## 3. IMPLEMENTATION STATUS DETAILS

### Complete & Production-Ready (6 endpoints)
1. ✅ **GET /v2/stamps/{scorer_id}/score/{address}** - Full scoring with API key auth
2. ✅ **GET /internal/embed/score/{scorer_id}/{address}** - Get score with stamps
3. ✅ **POST /internal/embed/stamps/{address}** - Add stamps and rescore
4. ✅ **GET /internal/embed/validate-api-key** - Validate partner API key
5. ✅ **POST /ceramic-cache/stamps/bulk** - Add stamps with JWT auth
6. ✅ **GET /ceramic-cache/score/{address}** - Get score with JWT auth

### Complete & Ready for Testing (9 endpoints)
7. ✅ **GET /internal/score/v2/{scorer_id}/{address}** - Internal scoring (no human points)
8. ✅ **GET /internal/embed/weights** - Weights retrieval (no auth)
9. ✅ **POST /internal/check-bans** - Ban checking
10. ✅ **POST /internal/check-revocations** - Revocation checking
11. ✅ **GET /internal/allow-list/{list}/{address}** - Allow list checking
12. ✅ **GET /internal/customization/credential/{provider_id}** - Credential definitions
13. ✅ **GET /internal/stake/gtc/{address}** - GTC stake retrieval
14. ✅ **GET /internal/stake/legacy-gtc/{address}/{round_id}** - Legacy GTC retrieval
15. ✅ **GET /internal/cgrants/contributor_statistics** - Contributor stats

---

## 4. CURRENT TEST INFRASTRUCTURE

### Test Organization (from TESTING.md)

**Unit Tests** (No Database)
```bash
cargo test --lib
```
- Location: `src/**/*.rs` with `#[cfg(test)]` modules
- Coverage: Model conversions, calculations, pure logic

**Database Integration Tests** (Requires DB)
```bash
DATABASE_URL="postgresql://..." cargo test --lib -- --ignored
```
- Location: `src/db/tests.rs`
- Marked with `#[ignore]` to skip by default

**API Integration Tests** (Full HTTP)
```bash
DATABASE_URL="postgresql://..." cargo test
```
- Location: `tests/integration_test.rs`, `tests/lifo_integration.rs`, `tests/test_human_points.rs`
- Tests: Health check, score endpoint, missing API key, invalid address

### Test Database Setup
```bash
# 1. Create test database
psql -U postgres -h localhost -c "CREATE DATABASE passport_scorer_test;"

# 2. Run Django migrations
cd api && poetry run python manage.py migrate --database=default

# 3. Run tests with DATABASE_URL set
cd rust-scorer
DATABASE_URL="postgresql://user:pass@localhost/passport_scorer_test" cargo test
```

### Existing Load Testing Infrastructure
- **Python Scripts**: `load_tests/test_data/` - Test account/VC generation
- **K6 Scripts**: `load_tests/test_scripts/` - Load testing scenarios
- **Scripts**: 
  - `run_scorer_load_test.sh` - Python scorer load test
  - `run_iam_load_test.sh` - IAM load test
  
---

## 5. DEVELOPMENT ENVIRONMENT SETUP

### Current Docker Compose (docker-compose.yml)
```yaml
Services:
  - postgres: 5432 (main database)
  - postgres-data: 5433 (data model database)
  - redis: 6379 (cache)
  - api: 8002 (Django/Python scorer)
  - interface: 3001 (frontend)
  - verifier: 8001 (credential verification)
```

### Rust Development Setup
- **Docker Setup**: `rust-scorer/docker-compose.jaeger.yml` - Jaeger tracing with OTLP
  - Jaeger UI: 16686
  - OTLP HTTP: 4318
  - OTLP gRPC: 4317

- **Dev Setup Scripts**: `dev-setup/setup.sh` - Automated environment configuration
  - Detects container vs system environment
  - Creates PostgreSQL database
  - Runs Django migrations
  - Installs dependencies

### Database Connection Pooling
- Rust: max_connections=5 (RDS Proxy handles actual pooling)
- Connection timeout: 3 seconds
- Uses `sslmode=require` for RDS Proxy

---

## 6. KEY ARCHITECTURAL DIFFERENCES

### Python Implementation
- Async-first with Django async ORM (asgiref)
- Uses `async_to_sync` wrapper for embedding sync code
- Feature flags for A/B testing (FF_MULTI_NULLIFIER, etc.)
- Event recording via Django pre_save signals
- PBKDF2 API key hashing (2.5 second latency issue)

### Rust Implementation
- Async Tokio runtime with Axum HTTP framework
- Pure async/await (no async_to_sync)
- No feature flags (simplified logic)
- Explicit event recording calls
- SHA-256 fast path for API key validation (microsecond latency)
- Transactional guarantees with sqlx
- OpenTelemetry integration with ADOT Lambda layer support

### Shared Patterns
- Both use ceramic_cache V1 stamps only (V2 never implemented)
- Both use LIFO deduplication for hash-based conflict resolution
- Both support provider deduplication in score calculation
- Both track human points (all 15 action types)
- Both record SCORE_UPDATE events

---

## 7. COMPARISON TESTING STRATEGY

### Endpoints to Compare for Load Testing
1. **External V2 Score** - Primary comparison (with/without human points)
2. **Internal Embed Score** - Secondary (embed service performance)
3. **Ceramic Cache Score** - JWT auth performance comparison

### Metrics to Compare
| Metric | Python | Rust | Expected Improvement |
|--------|--------|------|---------------------|
| Cold start | 2-5s | <100ms | 20-50x |
| P50 latency | 100-200ms | <100ms | 1-2x |
| P95 latency | 500-1000ms | <200ms | 2-5x |
| P99 latency | 1500-2000ms | <500ms | 3-4x |
| Memory (Lambda) | 512MB+ | <256MB | 2x efficiency |

### Load Test Scripts Available
```bash
# Generate test data
cd load_tests/test_data
pipenv run python generate_test_accounts.py

# Run load test against Rust scorer
cd /workspace/project/load_tests
./run_scorer_load_test.sh <vus> <duration>
# Example: ./run_scorer_load_test.sh 10 5m

# Check results
# - summary.json (K6 metrics)
# - k6_metrics.csv (time-series data)
```

---

## 8. ROUTING AND DEPLOYMENT

### ALB Header-Based Routing
The Rust implementation uses X-Use-Rust-Scorer header for safe A/B testing:
```
Priority 2090-2093: Rust routes with X-Use-Rust-Scorer: true header
Priority 2100-2103: Python routes (fallback for missing header)
```

### Lambda Configuration
- **Runtime**: Custom container (Docker)
- **Architecture**: ARM64/Graviton2 (34% better price/performance)
- **Memory**: 512MB (Python), <256MB target (Rust)
- **Timeout**: 60 seconds
- **Environment**: Lambda-only CONN_MAX_AGE workarounds not needed

### VPC Configuration
- Private subnets for ALB
- RDS Proxy integration (connection pooling at database layer)
- ADOT Lambda layer for OpenTelemetry (no manual configuration needed)

---

## 9. KEY FILES FOR COMPARISON TESTING

### Rust Implementation
- Routes: `/workspace/project/rust-scorer/src/api/server.rs` (lines 178-242)
- Handlers:
  - External: `src/api/handlers/external.rs`
  - Internal: `src/api/handlers/internal.rs`
  - Embed: `src/api/embed.rs`
  - Ceramic Cache: `src/api/ceramic_cache.rs`
- Domain Logic: `src/domain/` (scoring, weights, bans, stakes, etc.)
- Database Ops: `src/db/` (read_ops.rs, write_ops.rs, queries/)

### Python Implementation
- V2 API: `/workspace/project/api/v2/api/api_stamps.py`
- Internal API: `/workspace/project/api/internal/api.py`
- Embed API: `/workspace/project/api/embed/api.py` and `/workspace/project/api/embed/lambda_fn.py`
- Ceramic Cache: `/workspace/project/api/ceramic_cache/api/v1.py`

### Testing & Load Tests
- Rust Tests: `rust-scorer/tests/`, `rust-scorer/src/db/tests.rs`
- Python Tests: `api/*/test/`
- Load Tests: `load_tests/` with K6 scripts and test data generators

---

## 10. CRITICAL IMPLEMENTATION NOTES FOR TESTING

### Authentication Parity
- **API Key**: Both use PBKDF2-SHA256 hashing (Python), SHA-256 fast path (Rust)
- **JWT (Ceramic Cache)**: HS256, DID format `did:pkh:eip155:1:0xADDRESS`
- **Internal**: No auth (private ALB already authenticated)

### Type Conversions
- `scorer_id` in API is `community_id` in database (1:1 mapping, naming artifact)
- Decimal precision: 5 decimal places in API responses
- Timestamps: ISO 8601 format, UTC timezone

### Human Points Configuration
- Environment variables: `HUMAN_POINTS_ENABLED`, `HUMAN_POINTS_START_TIMESTAMP`, `HUMAN_POINTS_MTA_ENABLED`
- 15 action types: ScoringBonus, HumanKeys, IdentityStaking*, CommunityStaking*, HumanTech*, MetamaskOg*
- Provider field: Empty string `""` for non-provider actions (Django CharField behavior)

### Critical Gotchas
1. **V2 Ceramic Cache**: V2 stamps never implemented - both code V1 only
2. **Connection Pooling**: RDS Proxy handles pooling, app keeps low connection count (5)
3. **Provider Deduplication**: Only first stamp per provider contributes weight
4. **LIFO Retry**: 5 attempts for IntegrityError on concurrent hash link claims
5. **Nullifier Filtering**: Rust doesn't implement Python's FF_MULTI_NULLIFIER feature flag

