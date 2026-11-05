# Database Performance

Performance bottlenecks, profiling guidance, and database connection issues.

## Database Query Optimization

### LOWER() Breaks Database Indexes in WHERE Clauses

CRITICAL PERFORMANCE ISSUE: Never use LOWER() on indexed columns in WHERE clauses. This prevents PostgreSQL from using indexes and forces full table scans.

**The Problem**:

When you apply a function to an indexed column in a WHERE clause, PostgreSQL cannot use the index:

```sql
-- WRONG - breaks index, causes full table scan
WHERE LOWER(staker) = LOWER($1)

-- CORRECT - uses index
WHERE staker = $1
```

**The Solution**:

1. Lowercase the input parameter in Rust code BEFORE the query
2. Use simple equality in SQL without functions
3. This matches Python's pattern exactly

**Python Pattern (CORRECT)**:

```python
def get_gtc_stake_for_address(address: str):
    address = address.lower()  # Lowercase BEFORE query
    return Stake.filter(Q(staker=address) | Q(stakee=address))  # Simple equality
```

**Rust Pattern (CORRECT)**:

```rust
// In handler layer
let address = address.to_lowercase();  // Lowercase BEFORE passing to domain

// In SQL query
WHERE staker = $1 OR stakee = $1  // Simple equality, uses indexes
```

**Affected Tables with Indexes**:

- stake_stake: indexed on staker, stakee
- ceramic_cache_ban: indexed on address
- registry_hashscorerlink: indexed on address
- registry_gtcstakeevent: indexed on staker

This bug was introduced in the Rust scorer implementation and affected multiple queries in stakes.rs (2 queries), bans.rs (1 query), and dedup.rs (1 query). All handlers already lowercase addresses before calling domain functions, making the LOWER() calls in SQL redundant AND harmful. See `rust-scorer/src/db/queries/stakes.rs`, `rust-scorer/src/db/queries/bans.rs`, `rust-scorer/src/db/queries/dedup.rs`, `api/stake/api.py`.

## Embed Lambda Performance Issues

### Cold Start and RDS Proxy Connection Acquisition

The embed Lambda (/internal/embed/score) is timing out after 60 seconds during load testing. The issue is NOT slow queries but RDS Proxy connection acquisition.

**Performance Breakdown**:

1. **Cold start**: 4.5 seconds (including 2.5s for loading secrets)
2. **Database operations**: Taking 15-20 seconds each, but NOT due to slow queries
3. **Root cause**: RDS Proxy connection acquisition, not query execution

**Key Evidence**:

- 15 second gap between "Using selector: EpollSelector" and first query
- 20 seconds for LIFO deduplication (likely connection wait)
- 16 seconds for saving stamps (again, connection wait)
- Missing CONN_MAX_AGE setting in Django config (defaults to 0 - new connection per request)
- Lambda calls close_old_connections() at start of each request

**RDS Proxy Default Configuration**:

The RDS Proxy is configured in the core-infra repo (not passport-scorer) with:
- MaxConnectionsPercent: 100% (of RDS instance max_connections)
- MaxIdleConnectionsPercent: 50%
- ConnectionBorrowTimeout: 120 seconds (potential issue!)
- InitQuery: None
- SessionPinningFilters: Default

**Suspected Issues**:

1. RDS Proxy connection borrow timeout of 120 seconds may be causing 15-20 second delays under load
2. Django's CONN_MAX_AGE=0 means creating new connection per request
3. Lambda's close_old_connections() pattern is necessary to avoid stale connections but adds overhead

**Query Optimization Candidate**:

The `HashScorerLink.objects.filter(hash__in=stamp_hashes, community=community)` query in lifo.py is a candidate for optimization, but the primary issue is connection acquisition. See `api/embed/lambda_fn.py`, `api/embed/api.py`, `api/account/deduplication/lifo.py`, `api/scorer/settings/base.py`.

## Django CONN_MAX_AGE and Lambda Issues

Django's CONN_MAX_AGE has known issues with AWS Lambda:

### The Problem

1. **Connection persistence**: CONN_MAX_AGE keeps connections open between requests, but Lambda can freeze the container between invocations
2. **Stale connections**: When Lambda unfreezes, the TCP connection may be dead but Django doesn't know
3. **Errors**: This causes "connection already closed" errors on the next request
4. **Mitigation**: That's why every Lambda handler calls close_old_connections() - to avoid stale connections

### RDS Proxy Role

The RDS Proxy is supposed to handle this by:
- Managing connection pooling at the proxy level
- Handling dead connections transparently
- But it's NOT configured in the passport-scorer repo - it's in the core-infra repo

### RDS Proxy Configuration

Default limits from AWS Console (RDS → Proxies → Configuration):
- **MaxConnectionsPercent**: 100% (of RDS instance max_connections)
- **MaxIdleConnectionsPercent**: 50%
- **ConnectionBorrowTimeout**: 120 seconds (may cause delays!)
- **InitQuery**: None
- **SessionPinningFilters**: Default

The connection borrow timeout of 120 seconds could be causing the 15-20 second delays seen under load testing. See `api/embed/lambda_fn.py`, `api/scorer/settings/base.py`.

## Performance Analysis for I/O-Bound Services

### Flamegraphs vs Distributed Tracing

Flamegraphs are CPU sampling profilers - they show where CPU time is spent but completely ignore I/O wait time. This makes them useless for analyzing I/O-heavy services like the rust-scorer which spends most time waiting on database queries.

For production latency analysis of I/O-bound services, you need:

1. **Distributed tracing** (OpenTelemetry) with wall-clock timing of operations
2. **Simple structured logging** with explicit timing measurements
3. **Observability platforms** (Datadog, AWS X-Ray, etc) that show waterfall charts with milliseconds

The tokio tracing spans show async runtime internals, not business logic timing. You need to explicitly create child spans or use timing measurements for each I/O operation to get useful data. See `rust-scorer/PRACTICAL_TRACING.md`.
