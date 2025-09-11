# Axum Route Parameter Syntax

## Axum 0.8 Changes

Axum 0.8 changed route parameter syntax from colon-based `:param` to brace-based `{param}`. 

### Correct Syntax
```rust
.route("/v2/stamps/{scorer_id}/score/{address}", get(score_address_handler))
```

### Incorrect (Old) Syntax
```rust
// This causes 'Path segments must not start with :' error
.route("/v2/stamps/:scorer_id/score/:address", get(score_address_handler))
```

The route handler extracts these parameters using `Path((scorer_id, address)): Path<(i32, String)>`.

See `rust-scorer/src/api/server.rs`