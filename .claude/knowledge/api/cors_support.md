# CORS Support for API Endpoints

## Rust Scorer CORS Configuration

Added CORS support to Rust scorer to fix browser access issues for ceramic cache endpoints.

### Configuration

Matches Python's permissive CORS settings:
- `CORS_ALLOW_ALL_ORIGINS = True` (allows any origin)
- Allows all methods (GET, POST, PATCH, DELETE, OPTIONS, etc.)
- Allows all headers

### Implementation

1. Added "cors" feature to tower-http dependency in Cargo.toml
2. Added CorsLayer to the Axum app with tower_http::cors::Any for all settings
3. Layer added before TraceLayer in the middleware stack

### Supported Origins

This fixes CORS errors when ceramic cache endpoints are called from:
- https://app.passport.xyz
- https://app.review.passport.xyz
- https://app.staging.passport.xyz
- localhost
- Any other origin (matches Python's allow-all approach)

See: `rust-scorer/Cargo.toml`, `rust-scorer/src/api/server.rs`, `api/scorer/settings/base.py`
