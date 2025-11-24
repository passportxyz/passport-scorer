# Rust Testing Workflow

## Test Organization

Tests are organized in three categories:

1. **Unit tests (no DB)**: Run with `cargo test --lib`
2. **Database integration tests**: Marked with #[ignore], run with `DATABASE_URL="postgresql://..." cargo test --lib -- --ignored`
3. **API integration tests**: In tests/ directory, need DATABASE_URL

## Database Setup

Database setup requires:

1. Create database:
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

## Important Notes

- Tests use shared database (not sqlx::test isolation)
- Changed from #[sqlx::test] to #[tokio::test] with #[ignore] because sqlx::test creates isolated DBs without Django tables
- Database tests require Django migrations to be run first

See `rust-scorer/src/db/tests.rs`, `rust-scorer/tests/integration_test.rs`
