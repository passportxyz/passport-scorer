# Phase 7 Function Signature Alignment

## Database Operation Signatures

Phase 7 required fixing function signatures across the codebase for consistent database access patterns:

### Read Operations (use &PgPool)
- `load_community(scorer_id: i32, pool: &PgPool)`
- `load_ceramic_cache(address: &str, pool: &PgPool)`
- `get_latest_stamps_per_provider(address: &str, scorer_id: i32, pool: &PgPool)`

### Write Operations (use &mut Transaction)
- `upsert_passport(address: &str, scorer_id: i32, tx: &mut Transaction<'_, Postgres>)`
- `delete_stamps(passport_id: i32, tx: &mut Transaction<'_, Postgres>)`
- `bulk_insert_stamps(stamps: &[ValidStamp], passport_id: i32, tx: &mut Transaction<'_, Postgres>)`
- `upsert_score(score: &DjangoScore, tx: &mut Transaction<'_, Postgres>)`

### Special Cases
- `lifo_dedup(&stamps, address, scorer_id, &weights, tx)` - needs weights parameter
- `calculate_score(lifo_result)` - takes LifoResult directly, not separate valid/clashing stamps
- Human Points functions (`get_user_points_data`, `get_possible_points_data`) use &PgPool not transaction

## Key Insight

API handler must load scorer weights before calling lifo_dedup since weights are needed for the deduplication process.

See `rust-scorer/src/api/handler.rs`, `rust-scorer/src/db/read_ops.rs`, `rust-scorer/src/db/write_ops.rs`