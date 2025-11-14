# Ceramic Cache V2 Never Implemented

## [2025-11-14] V1 stamps only - V2 never implemented

The ceramic_cache table has a type field with enum values V1 and V2, but V2 stamps were never actually implemented. All Python code exclusively uses CeramicCache.StampType.V1.

### Key Points

- The ceramic_cache table has a type field with enum values ('V1', 'V2')
- V2 stamps were never actually implemented in production
- All Python code exclusively uses `CeramicCache.StampType.V1`
- V2 was a direction that was started but then abandoned

### Implementation Requirements

For the Rust scorer expansion, we should:
- Always filter for `type = 'V1'` in ceramic_cache queries
- Don't implement V2 support as it's not needed
- Can hardcode V1 type filtering in database queries

See: `api/ceramic_cache/api/v1.py`, `api/ceramic_cache/models.py`, `RUST_SCORER_EXPANSION_IMPLEMENTATION_GUIDE.md`