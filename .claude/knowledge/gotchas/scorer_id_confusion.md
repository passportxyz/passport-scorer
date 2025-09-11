# Scorer ID vs Community ID Confusion

## [2025-09-11] The scorer_id vs community_id naming confusion

CRITICAL: The API uses "scorer_id" but the database uses "community_id" for the same value. This is a historical artifact from when they planned 1:many communities:scorers, but it's actually 1:1.

### In Practice:
- **API endpoint**: `/v2/stamps/{scorer_id}/score/{address}` 
- **Database queries**: Use community_id = scorer_id value from API
- **scorer_weighted_binaryweightedscorer table**: Uses scorer_ptr_id which maps to community.id
- **registry_passport, registry_hashscorerlink, etc**: Use community_id

The Python code handles this by using the scorer_id from the API as community_id in database queries. The Rust code needs to do the same - treat the scorer_id parameter as community_id when querying the database.

See `rust-scorer/src/db/read_ops.rs`, `rust-scorer/src/api/handler.rs`