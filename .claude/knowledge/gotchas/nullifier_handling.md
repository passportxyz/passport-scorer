# Nullifier Handling Gotchas

## [2025-09-09] Python Nullifier Feature Flag

The Python `get_nullifiers` function in `lifo.py` has a feature flag `FF_MULTI_NULLIFIER` that controls whether all nullifiers are used or only v0-prefixed ones:
- When OFF (default): only nullifiers starting with 'v0' are used for deduplication
- The nullifiers come from `credential.credentialSubject.nullifiers` array or `.hash` field
- See `api/account/deduplication/lifo.py:38-44`

## [2025-09-09] Rust Migration - Nullifiers Array Only

The Rust implementation will ONLY support the nullifiers array field (not the legacy hash field):
- All credentials must have `credentialSubject.nullifiers` as an array with 1 or more values
- This simplifies the implementation compared to Python which handles both hash and nullifiers fields
- Documented in RUST_MIGRATION_PLAN.md

## [2025-09-09] Rust Migration - No Feature Flag for Nullifiers

The Rust implementation will NOT implement the `FF_MULTI_NULLIFIER` feature flag:
- It will always process ALL nullifiers in the array without any v0 prefix filtering
- This is a simplification from the Python implementation which conditionally filters nullifiers based on the feature flag
- Documented in RUST_MIGRATION_PLAN.md

## [2025-09-09] LIFO Deduplication Complexity

The Python LIFO implementation has complex logic:
1. Supports both legacy 'hash' field and newer 'nullifiers' array in credentialSubject
2. Uses FF_MULTI_NULLIFIER feature flag to filter nullifiers (only v0 prefixed when off)
3. A stamp is deduped if ANY of its nullifiers clash with existing hash links
4. When some but not all nullifiers clash, it backfills non-clashing nullifiers with the clashing owner's data
5. Implements 5-retry mechanism for IntegrityError handling on concurrent requests
6. Updates expired hash links by reassigning to new owner

This is simplified in the Rust plan to only support nullifiers array with no filtering.
See `api/account/deduplication/lifo.py`