# Rust Scorer Missing Customization Dynamic Weights

## [2026-02-10] Custom credential weights not merged in Rust

The Rust scorer's `load_scorer_config()` in `domain/scoring.rs` does NOT merge customization dynamic weights from the `account_customcredential` and `account_allowlist` tables.

### Python Behavior
The Python implementation (`scorer_weighted/computation.py:39-43`) calls `customization.get_customization_dynamic_weights()` which:
1. Queries `account_customcredential` table for custom credential weights
2. Queries `account_allowlist` table for allow list weights
3. Merges both into the scorer weights dict

### Impact
Any custom credentials (DeveloperList, NFT, etc.) and allow list weights are IGNORED in the Rust scoring path.

### Current Risk
Production currently routes 0% to Rust, so no immediate impact. This MUST be fixed before increasing Rust traffic for communities with custom credentials.

### Fix Required
Add calls in Rust's scoring config loading to:
1. Query `account_customcredential` → `account_customcredentialruleset` for provider_id and weight
2. Query `account_allowlist` → `account_addresslistmember` for allow list weights
3. Merge these into the weights dict before scoring

See: `rust-scorer/src/domain/scoring.rs`, `api/scorer_weighted/computation.py`, `api/account/models.py`
