# HTTP Error Handling

## Status Code Mapping

To return proper HTTP status codes, the error handling chain is:

```rust
DatabaseError → ApiError → HTTP Response
```

### Database Error Variants
- `DatabaseError::Unauthorized` → Missing/invalid API key
- `DatabaseError::InvalidData` → Bad request data
- `DatabaseError::NotFound` → Resource not found

### API Error Mapping
- `DatabaseError::Unauthorized` → `ApiError::Unauthorized` → 401 status
- `DatabaseError::InvalidData` → `ApiError::Validation` → 400 status  
- `DatabaseError::NotFound` → `ApiError::NotFound` → 404 status

## Implementation Note

Without the Unauthorized variant, missing API keys incorrectly returned 400 (Bad Request) instead of 401 (Unauthorized).

See `rust-scorer/src/db/errors.rs`, `rust-scorer/src/api/error.rs`, `rust-scorer/src/auth/api_key.rs`