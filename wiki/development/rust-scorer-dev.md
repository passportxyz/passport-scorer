# Rust Scorer Development Guide

## Clean Architecture Pattern

The Rust scorer implements a three-layer architecture for clean separation of concerns:

### Three-Layer Architecture

1. **API Layer** (`src/api/handlers/`)
   - HTTP concerns only (authentication, request parsing, response formatting)
   - Thin handlers that just orchestrate
   - NO business logic
   - Examples: external.rs (104 lines), internal.rs (510 lines), embed.rs (202 lines), ceramic_cache.rs (460 lines)

2. **Domain Layer** (`src/domain/`)
   - Shared business logic, no HTTP types
   - Takes primitives or domain types as input
   - Returns domain types (Result<T, DomainError>)
   - Used by BOTH internal and external handlers
   - Examples: scoring.rs, bans.rs, stakes.rs, weights.rs

3. **Data Layer** (`src/db/`)
   - Raw SQL queries in `db/queries/`
   - Database result types in `db/models/`
   - Transaction management
   - Domain-specific query modules (bans.rs, stakes.rs, cgrants.rs)

### Example Data Flow

```
External API → Handler (auth required) → domain::scoring::calculate() → db::queries
Internal API → Handler (no auth) → domain::scoring::calculate() → db::queries
```

Both use exact same business logic, just different auth at handler level.

## Benefits of This Architecture

- **Shared logic** = No duplication (ban checking used by 3+ endpoints)
- **Thin handlers** = Easy to test (can mock domain layer)
- **Clean boundaries** = Maintainable (changes don't cascade)
- **Future flexibility** = Easy to add GraphQL/gRPC (new handlers, same logic)

## Testing Strategy

### Test Organization

Tests are organized in three categories:

1. **Unit tests (no DB)**: Run with `cargo test --lib`
2. **Database integration tests**: Marked with `#[ignore]`, run with:
   ```bash
   DATABASE_URL="postgresql://..." cargo test --lib -- --ignored
   ```
3. **API integration tests**: In `tests/` directory, need DATABASE_URL

### Database Setup for Tests

1. Create test database:
   ```bash
   psql -U postgres -h localhost -c "CREATE DATABASE passport_scorer_test;"
   ```

2. Run Django migrations:
   ```bash
   cd api && poetry run python manage.py migrate --database=passport_scorer_test
   ```

3. Set DATABASE_URL and run tests:
   ```bash
   DATABASE_URL="postgresql://user:pass@localhost/passport_scorer_test" cargo test --lib -- --ignored
   ```

### Important Testing Notes

- Tests use shared database (not sqlx::test isolation)
- Changed from `#[sqlx::test]` to `#[tokio::test]` with `#[ignore]` because sqlx::test creates isolated DBs without Django tables
- Database tests require Django migrations to be run first

## Comparison Testing

### Python/Rust Equivalence Testing

The `rust-scorer/comparison-tests/` infrastructure validates Python/Rust response equivalence.

#### Features

- Auto-loads `.env.development` using dotenvy
- Starts both Python (8002) and Rust (3000) servers
- Compares JSON responses with sorted keys
- All 13/13 tests passing (as of Nov 2025)

#### Configuration Requirements

- Scorer type must be 'WEIGHTED_BINARY' not 'BinaryWeightedScorer'
- CERAMIC_CACHE_SCORER_ID required in env
- DATABASE_URL needs `?sslmode=disable` for local PostgreSQL
- Redis/Valkey required for Django caching

#### Test Categories

1. **Simple GET endpoints** (weights, allow-list) - ✓ Complete
2. **Scoring endpoints** with valid credentials, API key auth - ✓ Complete
3. **POST endpoints** (bans, revocations, add stamps) - ✓ Complete
4. **Complex endpoints** (cgrants statistics) - ✓ Complete

#### Running Comparison Tests

```bash
cd rust-scorer/comparison-tests
cargo run --release
```

## Code Organization

### Current Structure (7,599 lines total)

- **Handlers**: 1,176 lines (api/handlers/*.rs)
  - external.rs (104 lines)
  - internal.rs (510 lines)
  - embed.rs (202 lines)
  - ceramic_cache.rs (460 lines)
- **Domain**: 2,500+ lines (domain/*.rs)
- **Database**: 1,000+ lines (db/*.rs)
- **Models**: 988 lines
- **Tests**: 400+ lines

### Identified Code Quality Issues

#### Critical Duplications

1. **Address validation function** - defined 3 times
   - Locations: handlers/external.rs, handlers/internal.rs, api/utils.rs
   - Solution: All handlers should use the utils version
   - Risk: Inconsistent validation if drift occurs

2. **Error transformation pattern** - duplicated 20+ times
   - Same 7-line match pattern for DomainError -> ApiError
   - Locations: external.rs, internal.rs, embed.rs, ceramic_cache.rs
   - Solution: Create helper function for transformation

3. **Scoring request pattern** - duplicated in 5+ handlers
   - Pattern: Validate address → Call domain logic → Transform error → Return JSON
   - Solution: Extract into shared helper function

#### Response Type Consistency

- Most handlers: `ApiResult<Json<T>>`
- Exception: ceramic_cache add_stamps returns `(StatusCode::CREATED, Json<T>)` for API compatibility

### What's Working Well

- Three-layer architecture: API → Domain → Database is clean
- Error types: Properly designed with From implementations
- Domain modules: Well-organized by concern
- Test coverage: Adequate (models, db, handlers)
- Strong type system: Effective use throughout

### High Priority Cleanup Tasks

1. Remove duplicate address validation (handlers use utils version)
2. Create error transformation helper to replace 20+ duplicates
3. Delete dead shell scripts (stub_sqlx.sh, uncomment_queries.sh)

### Medium Priority Improvements

1. Extract scoring logic helper for common pattern

## Implementation Principles

1. **LIVE MIGRATION** - exact behavior match, no logic changes
2. Clean separation of concerns (handlers → domain → database)
3. Reuse existing connection pool and infrastructure
4. Group related endpoints in same module (e.g., all stake endpoints in stakes.rs)

## Key Design Decisions

- All internal endpoints in same Lambda as existing rust-scorer (simpler deployment)
- No authentication needed for internal endpoints (internal ALB handles this)
- Match Python's empty data behavior exactly (return empty arrays, not 404s)
- Use prepared statements and recommend indexes for performance

## Codebase Quality Baseline

- Code quality: 7.5→8.5/10 (with improvements)
- Maintainability: 7→8/10 (with cleanup tasks)
- Test coverage: Adequate across layers
- Performance: Rust implementation shows 20-50x speedup vs Python

## References

- `/rust-scorer/src/api/handlers/` - Handler layer
- `/rust-scorer/src/domain/` - Business logic
- `/rust-scorer/src/db/` - Database queries
- `/rust-scorer/comparison-tests/` - Python/Rust equivalence tests
- `/RUST_MIGRATION_PLAN.md` - Overall migration plan
- `/INTERNAL_API_RUST_MIGRATION_GUIDE.md` - Internal API implementation details
