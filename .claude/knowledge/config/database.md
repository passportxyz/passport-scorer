# Database Configuration

## Django Database Connections

Django uses multiple database connections:

- **default**: Main database from DATABASE_URL env var
- **data_model**: Separate DB for data model from DATA_MODEL_DATABASE_URL
- **read_replica_0**: Read replica from READ_REPLICA_0_URL
- **read_replica_analytics**: Analytics read replica from READ_REPLICA_ANALYTICS_URL

### Connection Pooling

No explicit connection pooling or CONN_MAX_AGE settings found in base.py, meaning Django uses default behavior (new connection per request). In Lambda, connections are closed after each request via `close_old_connections()`.

### Rust Implementation Note

For Rust: RDS Proxy handles connection pooling at infrastructure level, so low connection count (5) in app is appropriate.

See `api/scorer/settings/base.py` and `api/v2/aws_lambdas/stamp_score_GET.py`