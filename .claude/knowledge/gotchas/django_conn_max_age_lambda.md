# Django CONN_MAX_AGE and Lambda Issues

## [2025-11-14] Django CONN_MAX_AGE and Lambda Issues

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

The connection borrow timeout of 120 seconds could be causing the 15-20 second delays seen under load testing.

See: `api/embed/lambda_fn.py`, `api/scorer/settings/base.py`