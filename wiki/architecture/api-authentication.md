# API Authentication

API keys use Django's password hashing system with PBKDF2-SHA256 and optional SHA-256 fast path for improved performance.

## Key Storage Structure

- **Prefix**: First 8 characters for lookup
- **Hashed key**: PBKDF2-SHA256 (600,000 iterations) with auto-migration to SHA-256
- **Permissions**: submit_passports, read_scores, create_scorers, historical_endpoint
- **Rate limits**: Separate limits for standard, analysis, and embed endpoints
- **Analytics tracking**: Via account_accountapikeyanalytics table

## Key Format

- Format: `prefix.secret_key`
- Lookup uses prefix (8 chars)
- Storage uses Django's default password hashing format
- Validation via constant-time comparison

## Authentication Flow

1. Check X-API-Key header first, then Authorization header
2. Look up prefix in account_accountapikey table
3. Verify against hashed_key field
4. Check read_scores permission for scoring endpoints
5. Special handling for DEMO_API_KEY_ALIASES environment variable

## Database Tables

- **account_accountapikey**: Stores API keys with permissions, rates limits, and hashed keys
  - Fields: id (VARCHAR 150), account_id (BIGINT), hashed_key, hashed_key_sha256, permissions, rates, active
- **account_accountapikeyanalytics**: Usage tracking
  - Fields: api_key_id, path, method, status_code, error, created_at

## SHA-256 Fast Path Performance Optimization

Implemented dual-path verification for 11,000x+ performance improvement:

- **SHA-256 fast path**: ~0.004ms per verification (primary)
- **PBKDF2 fallback**: ~88ms per verification (unmigrated keys)
- **Auto-migration**: On successful PBKDF2 verification, system spawns async task to populate hashed_key_sha256
- **Backward compatible**: 100% compatible with existing API keys
- **Migration transparent**: No user action required

### Hash Format

- SHA-256 stored as: `sha256$<64-character-hex-digest>`
- Total length: 71 characters

### Failed Authentication Tracking

Comprehensive analytics for failed auth attempts:

- No API key provided (both headers missing)
- Invalid header format
- Key prefix not found
- Hash verification failure
- Missing read_scores permission

All failures tracked with error="Unauthorized request" and status_code=401.

## Rust Implementation

Matches Python exactly with:
- SHA-256 fast path when hashed_key_sha256 is populated
- PBKDF2-SHA256 verification for unmigrated keys
- Auto-migration spawned as background task
- Comprehensive failed auth tracking

Implementation: `rust-scorer/src/auth/api_key.rs`
