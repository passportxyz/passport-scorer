# Rust Scorer Endpoints Exploration Index

This document provides an index to the comprehensive exploration of Rust vs Python endpoint implementations and comparison testing infrastructure.

## Core Documents (NEW - Created During This Exploration)

### 1. RUST_PYTHON_ENDPOINTS_COMPARISON.md
**Length:** 397 lines  
**Purpose:** Complete technical reference for endpoint comparison testing

**Contents:**
- Comprehensive endpoint comparison matrix (15 endpoints total)
- Request/response format details with JSON examples
- Implementation status for each endpoint
- Test infrastructure description
- Development environment setup
- Key architectural differences (Python vs Rust)
- Comparison testing strategy with performance baselines
- Routing and deployment configuration
- Critical implementation notes for testing

**Use This When:** You need detailed technical specifications, request/response formats, or implementation status.

### 2. RUST_DEVELOPMENT_QUICKSTART.md
**Length:** 213 lines  
**Purpose:** Practical guide for getting started with Rust scorer development

**Contents:**
- Running Python and Rust simultaneously (port 8002 vs 3000)
- Quick database setup (5 commands)
- Test execution commands (unit, integration, load)
- Key endpoints to test with curl examples
- How to generate API keys for testing
- Load testing with K6 scripts
- Common development tasks
- Environment variables needed
- File locations reference
- Performance baselines
- Debugging tips

**Use This When:** You're setting up a dev environment or want quick commands to test endpoints.

---

## Implementation Files Reference

### Rust Endpoints Implementation

| Component | File(s) | Purpose |
|-----------|---------|---------|
| **Routes** | `rust-scorer/src/api/server.rs` (lines 178-242) | All 15 endpoint routes |
| **External Handler** | `rust-scorer/src/api/handlers/external.rs` | API key authenticated scoring |
| **Internal Handlers** | `rust-scorer/src/api/handlers/internal.rs` | 9 internal API endpoints |
| **Embed Handlers** | `rust-scorer/src/api/embed.rs` | 3 embed endpoints (get score, add stamps, validate key) |
| **Ceramic Cache** | `rust-scorer/src/api/ceramic_cache.rs` | JWT authenticated endpoints |
| **Domain Logic** | `rust-scorer/src/domain/` | Business logic (scoring, bans, stakes, cgrants, weights) |
| **Database Ops** | `rust-scorer/src/db/` | SQL queries and write operations |

### Python Endpoints Reference

| Component | File(s) | Purpose |
|-----------|---------|---------|
| **V2 API** | `api/v2/api/api_stamps.py` | Main scoring endpoint |
| **Internal API** | `api/internal/api.py` | Check bans, revocations, weights, stakes, cgrants |
| **Embed API** | `api/embed/api.py`, `api/embed/lambda_fn.py` | Embed operations |
| **Ceramic Cache** | `api/ceramic_cache/api/v1.py` | Stamp operations |

### Testing Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| **Rust Unit Tests** | `rust-scorer/src/db/tests.rs` + inline | Pure logic tests |
| **Rust Integration Tests** | `rust-scorer/tests/integration_test.rs` | HTTP endpoint tests |
| **LIFO Tests** | `rust-scorer/tests/lifo_integration.rs` | Deduplication tests |
| **Human Points Tests** | `rust-scorer/tests/test_human_points.rs` | Points calculation tests |
| **Load Tests** | `load_tests/test_scripts/` | K6-based load generation |
| **Test Data** | `load_tests/test_data/` | Account and VC generators |

---

## Endpoint Summary

### Quick Reference - All 15 Endpoints

**External (1):**
1. `GET /v2/stamps/{scorer_id}/score/{address}` - Primary scoring with API key

**Embed (3):**
2. `GET /internal/embed/score/{scorer_id}/{address}` - Get score with stamps
3. `POST /internal/embed/stamps/{address}` - Add stamps and rescore
4. `GET /internal/embed/validate-api-key` - Validate partner API key

**Ceramic Cache (2):**
5. `POST /ceramic-cache/stamps/bulk` - Add stamps with JWT
6. `GET /ceramic-cache/score/{address}` - Get score with JWT

**Internal API (9):**
7. `GET /internal/score/v2/{scorer_id}/{address}` - Internal scoring
8. `GET /internal/embed/weights` - Scorer weights
9. `POST /internal/check-bans` - Ban checking
10. `POST /internal/check-revocations` - Revocation checking
11. `GET /internal/allow-list/{list}/{address}` - Allow list checking
12. `GET /internal/customization/credential/{provider_id}` - Credential definitions
13. `GET /internal/stake/gtc/{address}` - GTC stakes
14. `GET /internal/stake/legacy-gtc/{address}/{round_id}` - Legacy GTC
15. `GET /internal/cgrants/contributor_statistics` - Contributor stats

---

## Development Environment

### Docker Compose Services

**Main Stack** (`docker-compose.yml`):
- `postgres:5432` - PostgreSQL main database
- `postgres-data:5433` - Data model database
- `redis:6379` - Cache
- `api:8002` - Python Django API
- `interface:3001` - Frontend
- `verifier:8001` - Credential verification

**Rust Development** (`rust-scorer/docker-compose.jaeger.yml`):
- `jaeger:16686` - Tracing UI
- `jaeger:4318` - OTLP HTTP endpoint
- `jaeger:4317` - OTLP gRPC endpoint

### Quick Start Commands

```bash
# Start Python API (requires docker)
docker-compose up postgres redis api

# Start Rust Scorer (requires PostgreSQL running)
cd rust-scorer && cargo run

# Run Rust unit tests
cd rust-scorer && cargo test --lib

# Run integration tests (requires DATABASE_URL)
cd rust-scorer && DATABASE_URL="postgresql://..." cargo test

# Run load tests
cd load_tests && ./run_scorer_load_test.sh 10 5m
```

---

## Testing Strategy

### Comparison Testing Approach

1. **Setup Phase:**
   - Create test database with Django migrations
   - Generate test data (accounts, API keys, scorers)
   - Start both Python (port 8002) and Rust (port 3000)

2. **Endpoint Testing:**
   - Hit same address against both implementations
   - Compare JSON responses (should be identical)
   - Measure latencies separately
   - Check error handling edge cases

3. **Load Testing Phase:**
   - Run K6 load test against both endpoints
   - Collect metrics in summary.json
   - Export time-series to k6_metrics.csv
   - Compare P50, P95, P99 latencies
   - Check cold start performance (Lambda)

4. **Validation:**
   - Response format parity
   - Score calculation results match
   - Stamps returned in same order
   - Error messages consistent
   - Human points calculations identical

### Performance Baselines

Expected improvements (after warm-up):
- P50: 1-2x faster
- P95: 2-5x faster  
- P99: 3-4x faster
- Cold start: 20-50x faster
- Memory: 2x more efficient

---

## Key Architectural Insights

### Clean Separation of Concerns

**Handler Layer** (Thin HTTP Orchestration):
- Route matching
- Authentication/authorization
- Request parsing
- Response formatting
- No business logic

**Domain Layer** (Pure Business Logic):
- Scoring orchestration
- LIFO deduplication
- Human points calculation
- Ban/revocation checking
- Weight retrieval
- Stake calculations

**Database Layer** (SQL Operations):
- All SELECT queries in read_ops
- All INSERT/UPDATE in write_ops
- Domain-specific modules in queries/
- Transaction management

### Authentication Mechanisms

**API Key** (V2 endpoints):
- Python: PBKDF2-SHA256 (2.5s per verification)
- Rust: SHA-256 fast path + PBKDF2 fallback (<1ms)
- Authorization header or X-API-Key header

**JWT** (Ceramic cache endpoints):
- Both: HS256 algorithm
- Both: Extract address from DID claim format
- Example: `did:pkh:eip155:1:0xADDRESS`

**Internal** (Private ALB endpoints):
- No application authentication
- Network-level access control via ALB
- All traffic already inside VPC

---

## Critical Gotchas

1. **V2 Ceramic Cache**: V2 stamps never implemented - both only use V1
2. **Connection Pooling**: RDS Proxy handles pooling at database layer
3. **Provider Deduplication**: Only first stamp per provider contributes weight
4. **Null Handling**: Empty string for non-provider actions in human points
5. **Type Conversions**: scorer_id in API = community_id in database

---

## Next Steps

### For Comparison Testing
1. Read `RUST_PYTHON_ENDPOINTS_COMPARISON.md` for technical details
2. Follow `RUST_DEVELOPMENT_QUICKSTART.md` for setup
3. Run unit tests: `cargo test --lib`
4. Set up test database and run integration tests
5. Execute load tests and compare metrics

### For Production Deployment
1. Review routing configuration in infra/aws/
2. Understand header-based routing (X-Use-Rust-Scorer header)
3. Configure Lambda memory and timeouts
4. Set up ADOT Lambda layer for OpenTelemetry
5. Validate response parity before production cutover

### For Future Development
1. All endpoints have matching implementations
2. Domain logic is organized by concern (scoring, bans, stakes, etc.)
3. Add new endpoints by following handler → domain → database pattern
4. Extend load tests with additional scenarios as needed

---

## File Locations Summary

### Documentation Files
- `/workspace/project/RUST_PYTHON_ENDPOINTS_COMPARISON.md` - Technical reference
- `/workspace/project/RUST_DEVELOPMENT_QUICKSTART.md` - Developer guide
- `/workspace/project/ENDPOINTS_EXPLORATION_INDEX.md` - This file

### Architecture Knowledge
- `/workspace/project/.claude/knowledge/architecture/` - Architecture documentation
- `/workspace/project/.claude/knowledge/api/` - API specifications
- `/workspace/project/.claude/knowledge/database/` - Database schema
- `/workspace/project/.claude/knowledge/patterns/` - Implementation patterns

### Implementation
- `/workspace/project/rust-scorer/src/api/` - HTTP handlers and routes
- `/workspace/project/rust-scorer/src/domain/` - Business logic
- `/workspace/project/rust-scorer/src/db/` - Database operations
- `/workspace/project/api/v2/api/` - Python reference implementation
- `/workspace/project/api/internal/` - Python internal API

### Testing
- `/workspace/project/rust-scorer/tests/` - Integration tests
- `/workspace/project/load_tests/` - Load testing infrastructure
- `/workspace/project/load_tests/test_scripts/` - K6 load test scenarios

---

## Quick Reference Links

- **Start Development**: Read `RUST_DEVELOPMENT_QUICKSTART.md`
- **Understand Endpoints**: Read `RUST_PYTHON_ENDPOINTS_COMPARISON.md`
- **Architecture Decisions**: Review `.claude/knowledge/` documents
- **Run Tests**: Follow commands in RUST_DEVELOPMENT_QUICKSTART.md
- **Load Test**: See `load_tests/run_scorer_load_test.sh`

---

Last Updated: November 19, 2025
All 15 endpoints fully implemented and ready for comparison testing
