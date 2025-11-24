# Database Query Performance Gotchas

## [2025-11-24] LOWER() Breaks Database Indexes in WHERE Clauses

**CRITICAL PERFORMANCE ISSUE**: Never use LOWER() on indexed columns in WHERE clauses. This prevents PostgreSQL from using indexes and forces full table scans.

### The Problem

When you apply a function to an indexed column in a WHERE clause, PostgreSQL cannot use the index:

```sql
-- WRONG - breaks index, causes full table scan
WHERE LOWER(staker) = LOWER($1)

-- CORRECT - uses index
WHERE staker = $1
```

### The Solution

1. Lowercase the input parameter in Rust code BEFORE the query
2. Use simple equality in SQL without functions
3. This matches Python's pattern exactly

### Python Pattern (CORRECT)

```python
def get_gtc_stake_for_address(address: str):
    address = address.lower()  # Lowercase BEFORE query
    return Stake.filter(Q(staker=address) | Q(stakee=address))  # Simple equality
```

### Rust Pattern (CORRECT)

```rust
// In handler layer
let address = address.to_lowercase();  // Lowercase BEFORE passing to domain

// In SQL query
WHERE staker = $1 OR stakee = $1  // Simple equality, uses indexes
```

### Affected Tables with Indexes

- stake_stake: indexed on staker, stakee
- ceramic_cache_ban: indexed on address
- registry_hashscorerlink: indexed on address
- registry_gtcstakeevent: indexed on staker

### Historical Context

This bug was introduced in the Rust scorer implementation and affected multiple queries:
- stakes.rs (2 queries)
- bans.rs (1 query)
- dedup.rs (1 query)

All handlers already lowercase addresses before calling domain functions, making the LOWER() calls in SQL redundant AND harmful.

See: `rust-scorer/src/db/queries/stakes.rs`, `rust-scorer/src/db/queries/bans.rs`, `rust-scorer/src/db/queries/dedup.rs`, `api/stake/api.py`
