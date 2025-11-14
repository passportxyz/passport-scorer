# Embed Lambda Performance Issues

## [2025-11-14] Cold Start and RDS Proxy Connection Issues

The embed Lambda (/internal/embed/score) is timing out after 60 seconds during load testing.

### Performance Breakdown

1. **Cold start**: 4.5 seconds (including 2.5s for loading secrets)
2. **Database operations**: Taking 15-20 seconds each, but NOT due to slow queries
3. **Root cause**: RDS Proxy connection acquisition, not query execution

### Key Evidence

- 15 second gap between "Using selector: EpollSelector" and first query
- 20 seconds for LIFO deduplication (likely connection wait)
- 16 seconds for saving stamps (again, connection wait)
- Missing CONN_MAX_AGE setting in Django config (defaults to 0 - new connection per request)
- Lambda calls close_old_connections() at start of each request

### RDS Proxy Default Configuration

The RDS Proxy is configured in the core-infra repo (not passport-scorer) with:
- MaxConnectionsPercent: 100% (of RDS instance max_connections)
- MaxIdleConnectionsPercent: 50%
- ConnectionBorrowTimeout: 120 seconds (potential issue!)
- InitQuery: None
- SessionPinningFilters: Default

### Suspected Issues

1. RDS Proxy connection borrow timeout of 120 seconds may be causing 15-20 second delays under load
2. Django's CONN_MAX_AGE=0 means creating new connection per request
3. Lambda's close_old_connections() pattern is necessary to avoid stale connections but adds overhead

### Query Optimization Candidate

The `HashScorerLink.objects.filter(hash__in=stamp_hashes, community=community)` query in lifo.py is a candidate for optimization, but the primary issue is connection acquisition.

See: `api/embed/lambda_fn.py`, `api/embed/api.py`, `api/account/deduplication/lifo.py`, `api/scorer/settings/base.py`