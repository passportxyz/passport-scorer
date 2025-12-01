# Internal API Database Schema

## Table Names (Actual Django Tables)

- `ceramic_cache_ban` - ban records with type, provider, hash, address, end_time
- `ceramic_cache_revocation` - revoked proof values
- `stake_stake` - GTC staking records with staker/stakee
- `registry_gtcstakeevent` - legacy staking events with staker/address fields (NOT stakee)
- `cgrants_grantcontributionindex` - grant contributions, joins to cgrants_contribution
- `cgrants_protocolcontributions` - protocol-level contributions
- `cgrants_squelchedaccounts` - addresses that should return zero stats
- `account_addresslist` / `account_addresslistmember` - allow list membership
- `account_customcredentialruleset` - custom credential definitions

## Performance Bottlenecks Identified

- Ban checks need compound index on (address, hash) with end_time filter
- Revocation checks are frequent and need index on proof_value
- CGrants queries are complex with multiple JOINs and aggregations
- Protocol contributions need compound index on (from_address, to_address)

## Field Type Gotchas

- GTCStakeEvent has 'staker' and 'address' fields, NOT 'stakee'
- GTCStakeEvent.staked is a boolean field
- All amounts should use Decimal type for precision
- Timestamps are timezone-aware (UTC)
- Empty provider names stored as empty string "", not NULL

## Query Optimization Notes

- CGrants endpoint makes 6 separate queries - consider CTE or parallel execution
- Use COALESCE for SUMs to handle NULL results as 0
- Protocol contributions need separate SUMs for from_address vs to_address
- Check squelched status first to potentially skip other queries

See: `api/extract_sql_queries_v2.py`, `INTERNAL_API_RUST_MIGRATION_GUIDE.md`
