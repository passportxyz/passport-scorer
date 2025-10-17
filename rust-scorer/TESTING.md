# Testing Guide for Rust Scorer

This guide explains how to run tests for the rust-scorer project.

## Test Organization

Tests are organized into three categories:

### 1. Unit Tests (No Database Required)
Fast tests that don't require database connections. These test pure logic like model conversions, calculations, etc.

**Location:**
- `src/models/tests.rs` - Model conversion tests
- `src/human_points/models.rs` - Human points logic tests
- Various inline `#[cfg(test)]` modules

**Run with:**
```bash
cargo test --lib
```

### 2. Database Integration Tests (Requires Database)
Tests that interact with the database but are marked with `#[ignore]` to skip by default.

**Location:**
- `src/db/tests.rs` - Database operation tests (upsert, hash links, etc.)

**Setup:**
```bash
# 1. Create test database
psql -U postgres -h localhost -c "CREATE DATABASE passport_scorer_test;"

# 2. Run Django migrations to set up schema
cd ../api && poetry run python manage.py migrate --database=default

# 3. Run ignored tests
cd ../rust-scorer
DATABASE_URL="postgresql://user:pass@localhost/passport_scorer_test" cargo test --lib -- --ignored
```

### 3. Integration Tests (Requires Database)
Full integration tests that test the complete API flow.

**Location:**
- `tests/integration_test.rs` - API endpoint tests, health checks
- `tests/lifo_integration.rs` - LIFO deduplication integration tests
- `tests/test_human_points.rs` - Human points processing tests

**Setup:**
```bash
# Use the same test database setup as above
DATABASE_URL="postgresql://user:pass@localhost/passport_scorer_test" cargo test
```

## Environment Variables

### Required
- `DATABASE_URL` - PostgreSQL connection string for tests
  - Example: `postgresql://postgres:password@localhost:5432/passport_scorer_test`

### Optional
- `TEST_DATABASE_URL` - Alternative to DATABASE_URL (falls back to DATABASE_URL if not set)
- `RUST_LOG` - Control log verbosity (e.g., `info`, `debug`)

## Running All Tests

```bash
# Unit tests only (fast, no DB)
cargo test --lib

# All tests including integration (requires DB)
DATABASE_URL="postgresql://user:pass@localhost/passport_scorer_test" cargo test

# Run ignored DB tests
DATABASE_URL="postgresql://user:pass@localhost/passport_scorer_test" cargo test --lib -- --ignored

# Run specific test
cargo test test_health_check

# Run with verbose output
cargo test -- --nocapture
```

## Test Database Management

**Important:** Tests use a shared database, not isolated transactions. This means:
- Tests may interfere with each other if they modify the same data
- Clean up may be needed between test runs
- Consider using unique test data (addresses, scorer_ids) in each test

**Reset test database:**
```bash
psql -U postgres -h localhost -c "DROP DATABASE passport_scorer_test;"
psql -U postgres -h localhost -c "CREATE DATABASE passport_scorer_test;"
cd ../api && poetry run python manage.py migrate --database=default
```

## Continuous Integration

For CI environments, ensure:
1. PostgreSQL service is available
2. Django migrations are run before tests
3. DATABASE_URL is set
4. Run both unit and integration tests

Example CI command:
```bash
# Run all tests
DATABASE_URL="${CI_DATABASE_URL}" cargo test --all-targets

# Or separate unit and integration
cargo test --lib  # Unit tests
DATABASE_URL="${CI_DATABASE_URL}" cargo test --lib -- --ignored  # DB tests
DATABASE_URL="${CI_DATABASE_URL}" cargo test  # Integration tests
```

## Common Test Patterns

### Testing with Mock Data
```rust
fn create_test_stamp(provider: &str, nullifiers: Vec<String>) -> ValidStamp {
    ValidStamp {
        provider: provider.to_string(),
        credential: json!({
            "credentialSubject": {
                "provider": provider,
                "nullifiers": nullifiers,
            },
        }),
        nullifiers,
        expires_at: Utc::now() + Duration::days(30),
    }
}
```

### Testing Async Code
```rust
#[tokio::test]
async fn test_async_function() {
    let result = my_async_function().await;
    assert!(result.is_ok());
}
```

### Testing with Database
```rust
#[tokio::test]
#[ignore] // Mark as ignored for DB-dependent tests
async fn test_database_operation() {
    let pool = setup_test_pool().await;
    // ... test code
}
```

## Test Coverage

Current test coverage includes:
- ✅ Model conversions (Django ↔ Internal ↔ API)
- ✅ LIFO deduplication logic
- ✅ Score calculation
- ✅ API authentication
- ✅ Human points processing
- ✅ Database operations (upsert, bulk insert, events)
- ✅ API endpoints (health check, scoring)

## Troubleshooting

### "Failed to connect to database"
- Ensure PostgreSQL is running
- Check DATABASE_URL is correct
- Verify test database exists

### "relation does not exist"
- Run Django migrations on test database
- Ensure you're using the correct database name

### Tests hang or timeout
- Check database connection pool settings
- Verify no long-running queries or deadlocks
- Use `-- --nocapture` to see detailed output

### "Address already in use" (for server tests)
- Another instance of the server may be running
- Change the PORT environment variable
- Kill any orphaned processes
