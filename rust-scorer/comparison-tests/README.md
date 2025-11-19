# Python <-> Rust Comparison Tests

Automated test harness that verifies Rust scorer endpoints return the same results as Python endpoints.

## Prerequisites

1. **Database running** with migrations applied:
   ```bash
   cd dev-setup
   ./start-postgres.sh
   ```

2. **Redis/Valkey running**:
   ```bash
   valkey-server --daemonize yes --port 6379
   ```

3. **Test data created**:
   ```bash
   cd api
   poetry run python ../dev-setup/create_test_data.py
   ```

4. **Ports 8002 and 3000 free** (the test runner starts both servers)

## Usage

```bash
cd rust-scorer/comparison-tests
cargo run --release
```

The test runner automatically loads `.env.development` from the project root using dotenvy.

The test runner will:
1. Start the Python Django server on port 8002
2. Start the Rust server on port 3000
3. Wait for both to be healthy
4. Run comparison tests
5. Report results and shut down servers

## Current Tests

- `GET /internal/embed/weights` - Stateless endpoint, no auth

## Adding New Tests

Edit `src/main.rs` and add calls to the `TestRunner`:

```rust
// For GET endpoints
test_runner.compare_get("My test name", "/path/to/endpoint").await?;
```

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Troubleshooting

### Python server won't start
- Check that poetry is installed and `api/` dependencies are installed
- Verify DATABASE_URL is set correctly

### Rust server won't start
- Run `cargo build` in `rust-scorer/` first to ensure it compiles
- Check that DATABASE_URL is set

### Tests fail with connection errors
- Ensure database is running
- Check that ports 8002 and 3000 are not in use
