# Rust Scorer Development Quick Start

## What You Need to Know

### Running Both Python and Rust Simultaneously

Both can run at the same time for comparison testing:
- **Python Django**: `docker-compose up` (port 8002)
- **Rust Scorer**: `cargo run` in `rust-scorer/` (port 3000 by default)

### Quick Database Setup

```bash
# 1. Start PostgreSQL (from docker-compose)
docker-compose up postgres

# 2. Create test database
psql -U passport_scorer -h localhost -d postgres -c "CREATE DATABASE passport_scorer_dev;"

# 3. Run Django migrations (creates schema)
cd api && poetry run python manage.py migrate

# 4. Start Rust scorer
cd rust-scorer && cargo run
```

### Running Tests

**Rust Unit Tests** (fast, no DB)
```bash
cd rust-scorer
cargo test --lib
```

**Rust Integration Tests** (requires DB)
```bash
cd rust-scorer
DATABASE_URL="postgresql://passport_scorer:passport_scorer_pwd@localhost/passport_scorer_dev" cargo test
```

**Python Tests**
```bash
cd api
poetry run pytest api/*/test/
```

### Key Endpoints to Test

| Endpoint | URL | Auth | Purpose |
|----------|-----|------|---------|
| **Health Check** | `GET http://localhost:3000/health` | None | Verify Rust scorer is running |
| **Score (External)** | `GET http://localhost:3000/v2/stamps/1/score/0x...` | API Key | Primary scoring endpoint |
| **Score (Internal)** | `GET http://localhost:3000/internal/score/v2/1/0x...` | None (private ALB) | Internal scoring |
| **Weights** | `GET http://localhost:3000/internal/embed/weights` | None | Get scorer weights |

### Getting an API Key for Testing

From Python Django shell:
```bash
cd api
poetry run python manage.py shell

# In shell:
from account.models import AccountAPIKey, Account, Community
account = Account.objects.first()
community = Community.objects.first()
api_key = AccountAPIKey.objects.create(
    account=account,
    name="test-key",
    community=community
)
print(api_key.get_key())  # This is the actual key to use
```

### Load Testing

```bash
# Generate test data
cd load_tests
pipenv run python test_data/generate_test_accounts.py

# Run load test (10 virtual users, 5 minute duration)
# Set SCORER_API_KEY and SCORER_ID environment variables first
./run_scorer_load_test.sh 10 5m

# Results in:
# - summary.json (test metrics)
# - k6_metrics.csv (time-series)
```

### Common Development Tasks

**Edit Rust code and reload**
```bash
cd rust-scorer
cargo watch -x run
```

**Debug failing test**
```bash
cd rust-scorer
RUST_LOG=debug cargo test test_name -- --nocapture
```

**Check Rust compilation without running**
```bash
cd rust-scorer
cargo check
```

**View database in Python**
```bash
cd api
poetry run python manage.py dbshell
# Then SQL: SELECT * FROM registry_score LIMIT 5;
```

### Environment Variables

For Rust scorer (in rust-scorer/ or .env):
```bash
DATABASE_URL=postgresql://passport_scorer:passport_scorer_pwd@localhost/passport_scorer_dev
RUST_LOG=info
PORT=3000
OTEL_ENABLED=false  # Disable OpenTelemetry for local dev
```

For Python API (in api/ or .env):
```bash
DATABASE_URL=postgresql://passport_scorer:passport_scorer_pwd@localhost/passport_scorer_dev
HUMAN_POINTS_ENABLED=true
```

### File Locations Reference

| What | Where |
|------|-------|
| Rust routes | `rust-scorer/src/api/server.rs` |
| Python V2 routes | `api/v2/api/api_stamps.py` |
| Shared scoring logic | `rust-scorer/src/domain/scoring.rs` |
| Python scoring logic | `api/registry/atasks.py` |
| Request/Response models | `rust-scorer/src/models/v2_api.rs` |
| Python response models | `api/v2/schema.py` |
| Load test scripts | `load_tests/test_scripts/` |

### Performance Baselines

Expected latencies (after warm-up):

| Scenario | Python | Rust | Improvement |
|----------|--------|------|-------------|
| Simple score lookup | 100-200ms | <50ms | 2-4x |
| Score with human points | 200-400ms | <100ms | 2-4x |
| Add stamps + score | 150-300ms | <75ms | 2-4x |
| Cold start (Lambda) | 2-5s | <100ms | 20-50x |

### Debugging Tips

1. **Check if Rust scorer is responding**:
   ```bash
   curl http://localhost:3000/health
   ```

2. **Compare responses (Python vs Rust)**:
   ```bash
   # Python (port 8002)
   curl "http://localhost:8002/v2/stamps/1/score/0x..." \
     -H "X-API-Key: $API_KEY"
   
   # Rust (port 3000)
   curl "http://localhost:3000/v2/stamps/1/score/0x..." \
     -H "X-API-Key: $API_KEY"
   ```

3. **View logs** (if running with docker):
   ```bash
   docker-compose logs api
   ```

4. **Check database schema**:
   ```bash
   psql -U passport_scorer localhost passport_scorer_dev
   \d registry_score
   ```

### Next Steps

1. Review the full endpoint comparison: `RUST_PYTHON_ENDPOINTS_COMPARISON.md`
2. Run unit tests: `cargo test --lib`
3. Set up test database and run integration tests
4. Try a comparison test with the load testing scripts
5. Review the architecture documentation in `.claude/knowledge/`

