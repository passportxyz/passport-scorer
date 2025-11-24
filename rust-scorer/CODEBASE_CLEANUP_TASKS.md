# Rust Scorer Codebase Cleanup Tasks

## ✨ Update (2024-11-24)
**High priority tasks 1-3 have been completed!**
- Implemented idiomatic Rust error handling with `From` trait and `?` operator
- Consolidated duplicate code and removed unnecessary helpers
- Cleaned up dead scripts

## Overview
This document outlines code quality improvements identified in the Rust scorer codebase. These tasks can be completed independently and incrementally. All changes should be validated using the comparison tests.

## High Priority Tasks

### 1. ✅ Remove Duplicate Address Validation Functions [COMPLETED]
**Problem:** The `is_valid_eth_address` function is duplicated in 3 places.

**Files to modify:**
- `src/api/handlers/external.rs` (lines 19-22) - Remove local function
- `src/api/handlers/internal.rs` (lines 51-54) - Remove local function

**Solution:**
1. Delete the local `is_valid_eth_address` functions from both files
2. Add `use crate::api::utils::is_valid_eth_address;` to both files
3. Ensure all handlers use the single version from `src/api/utils.rs`

**Testing:** Run comparison tests to ensure address validation still works correctly.

---

### 2. ✅ Create Error Transformation Helper Function [COMPLETED - IMPROVED]
**Problem:** Every handler repeats the same 8-line match block for converting `DomainError` to `ApiError`.

**Files affected:**
- `src/api/handlers/external.rs` (1 instance)
- `src/api/handlers/internal.rs` (8+ instances)
- `src/api/embed.rs` (2+ instances)
- `src/api/ceramic_cache.rs` (3+ instances)

**Solution:**
1. Add this helper function to `src/api/utils.rs`:
```rust
use crate::api::error::ApiError;
use crate::domain::DomainError;
use axum::Json;

pub fn transform_domain_result<T>(result: Result<T, DomainError>) -> Result<Json<T>, ApiError> {
    match result {
        Ok(response) => Ok(Json(response)),
        Err(DomainError::NotFound(msg)) => Err(ApiError::NotFound(msg)),
        Err(DomainError::Validation(msg)) => Err(ApiError::BadRequest(msg)),
        Err(DomainError::Database(msg)) => Err(ApiError::Database(msg)),
        Err(DomainError::Internal(msg)) => Err(ApiError::Internal(msg)),
    }
}
```

2. Replace all instances of the match block with:
```rust
transform_domain_result(result)
```

**Testing:** Run all comparison tests to ensure error handling still works correctly.

**ACTUAL SOLUTION IMPLEMENTED:** Instead of helper functions, we implemented `From<DomainError> for ApiError` trait in `src/api/error.rs`, allowing us to use the `?` operator throughout. This is more idiomatic Rust and eliminates ALL error transformation boilerplate.

---

### 3. ✅ Delete Dead Development Scripts [COMPLETED]
**Problem:** Old SQLX development scripts are no longer needed.

**Files to delete:**
- `stub_sqlx.sh`
- `uncomment_queries.sh`

**Solution:**
```bash
rm stub_sqlx.sh uncomment_queries.sh
```

**Testing:** Ensure the build still works: `cargo build --release`

---

## Medium Priority Tasks

### 4. ✅ Consolidate Handler Organization
**Problem:** Handler modules are inconsistently organized. Some are in `handlers/` directory, others are floating in `api/`.

**Current structure:**
```
src/api/handlers/external.rs ✓
src/api/handlers/internal.rs ✓
src/api/embed.rs ✗ (should be in handlers/)
src/api/ceramic_cache.rs ✗ (should be in handlers/)
```

**Solution:**
1. Move files:
```bash
mv src/api/embed.rs src/api/handlers/embed.rs
mv src/api/ceramic_cache.rs src/api/handlers/ceramic_cache.rs
```

2. Update `src/api/handlers/mod.rs`:
```rust
pub mod external;
pub mod internal;
pub mod embed;        // Add this
pub mod ceramic_cache; // Add this
```

3. Update `src/api/mod.rs` to remove the old module declarations:
```rust
// Remove these lines:
// pub mod embed;
// pub mod ceramic_cache;
```

4. Update imports in `src/api/server.rs`:
```rust
// Change from:
use crate::api::embed::{...};
use crate::api::ceramic_cache::{...};

// To:
use crate::api::handlers::embed::{...};
use crate::api::handlers::ceramic_cache::{...};
```

5. Remove or update the TODO comment in `server.rs` about migrating to new architecture.

**Testing:**
- Ensure compilation: `cargo build`
- Run comparison tests for embed and ceramic_cache endpoints

---

### 5. ✅ Standardize Response Types
**Problem:** Inconsistent response types across handlers.

**Current state:**
- Most handlers return: `Result<Json<T>, ApiError>`
- ceramic_cache handlers return: `Result<(StatusCode, Json<T>), ApiError>`

**Solution:**
Choose one approach and standardize:

**Option A (Recommended):** All handlers return `Result<Json<T>, ApiError>`
- Modify ceramic_cache handlers to return `Json<T>` instead of `(StatusCode, Json<T>)`
- The framework automatically sets StatusCode::OK for successful Json responses

**Option B:** All handlers return `Result<(StatusCode, Json<T>), ApiError>`
- Modify all other handlers to explicitly return `(StatusCode::OK, Json(response))`
- More verbose but gives explicit control over status codes

**Testing:** Run all comparison tests to ensure responses still match Python API.

---

## Low Priority Tasks (Optional)

### 6. ⭕ Extract Shared Scoring Logic Helper
**Problem:** Similar scoring flow logic appears in multiple handlers.

**Affected files:**
- `src/api/handlers/external.rs`
- `src/api/handlers/internal.rs`
- `src/api/embed.rs`
- `src/api/ceramic_cache.rs`

**Note:** This is lower priority because while there's similarity, each endpoint has slightly different requirements (auth, human points, response format).

---

## Validation Checklist

After completing any task:
- [ ] Code compiles: `cargo build --release`
- [ ] Unit tests pass: `cargo test --lib`
- [ ] Database tests pass: `cargo test --lib -- --ignored` (with DATABASE_URL set)
- [ ] Comparison tests pass: `cd comparison-tests && cargo run`
- [ ] No new clippy warnings: `cargo clippy`

## Notes
- Each task is independent and can be completed separately
- Estimated time: 15-30 minutes per task
- Total effort: 2-3 hours for all tasks
- Risk level: Low (comparison tests provide safety net)