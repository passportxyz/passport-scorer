# API Key Performance Optimization

## SHA-256 Fast Path Implementation

Implemented critical API key performance fix replacing PBKDF2 (600k iterations) with SHA-256 hashing. The fix provides 11,000-25,000x speedup while maintaining security for high-entropy API keys (190 bits).

### Key Implementation Details

1. **Dual-field approach**: Added `hashed_key_sha256` field to AccountAPIKey model for fast verification
2. **FastAPIKeyValidator class**: Implements dual-path verification (SHA-256 fast path, PBKDF2 fallback)
3. **Auto-migration**: On successful PBKDF2 verification, saves SHA-256 hash for future use
4. **Backward compatibility**: Maintains 100% compatibility with existing API keys
5. **Updated authentication paths**: Both sync (`ApiKey.authenticate`) and async (`aapi_key`) paths updated

### Performance Impact

- **SHA-256**: ~0.004ms per verification
- **PBKDF2**: ~88ms per verification
- **Speedup**: 11,000x+ in tests
- **API latency**: Reduces from 2.5s to <0.1s for authentication

### Migration Strategy

- Keys migrate transparently on first use after deployment
- No action required from API users
- Monitor migration progress via `hashed_key_sha256` field population
- Zero downtime migration

### Python Implementation Files

- `api/account/api_key_validator.py` - FastAPIKeyValidator class implementation
- `api/registry/api/utils.py` - Integration with API authentication flow
- `api/account/models.py` - AccountAPIKey model with new field
- `api/account/migrations/0044_add_hashed_key_sha256.py` - Database migration

## Rust Implementation

The Rust scorer implements the same SHA-256 fast path for API key verification, matching Python's behavior exactly.

### Data Model

- Added `hashed_key_sha256: Option<String>` field to `DjangoApiKey` struct
- Field stores SHA-256 hash in format "sha256$<64-char-hex>"
- Total 71 characters: "sha256$" (7) + 64 hex chars

### Verification Logic

- **Fast path**: SHA-256 verification (~0.004ms) when `hashed_key_sha256` is populated
- **Fallback path**: PBKDF2-SHA256 verification (~88ms) for unmigrated keys
- **Legacy support**: SHA512 verification for old djangorestframework-api-key v2 hashes
- Uses `VerificationResult` enum: `ValidSha256`, `ValidPbkdf2NeedsMigration`, `Invalid`

### Auto-Migration

- On successful PBKDF2 verification, spawns async task to update `hashed_key_sha256` field
- Fire-and-forget approach - doesn't block the request
- Migration logged with info level: "API key auto-migrated to SHA-256 for id: {}"

### Hash Format

- Matches Python exactly: `sha256${hashlib.sha256(full_key.encode()).hexdigest()}`
- 71 characters total: "sha256$" (7) + 64 hex chars

### Failed Authentication Analytics Tracking

Implemented comprehensive analytics tracking for failed authentication attempts to match Python's behavior:

1. **track_failed_auth Function**: Helper function to track failed auth attempts
   - Tries to look up API key by prefix to find `api_key_id`
   - Creates analytics record with NULL `api_key_id` for failed attempts
   - Sets `error="Unauthorized request"` and `status_code=401`
   - Fire-and-forget approach using `tokio::spawn`

2. **Failed Auth Tracking Points**:
   - No API key provided (both X-API-Key and Authorization headers missing)
   - Invalid Authorization header format (malformed "Bearer <key>")
   - Key not found (prefix doesn't exist or key is revoked/expired)
   - Invalid key (hash verification fails)
   - Insufficient permissions (API key lacks `read_scores` permission)

3. **Match Python Behavior**: Python's `track_usage(request, "", 401)` creates analytics with `api_key=None`, Rust's `track_failed_auth(pool, None, path)` matches exactly

### Testing

- 9 unit tests covering SHA-256, PBKDF2, SHA512 paths
- Tests for hash generation, verification, format detection
- All tests passing

### Rust Implementation Files

- `rust-scorer/src/auth/api_key.rs` - API key validation with SHA-256 fast path
- `rust-scorer/src/models/django.rs` - DjangoApiKey struct with hashed_key_sha256 field
- `rust-scorer/src/api/handler.rs` - Integration with API handler and analytics tracking

See `api/account/api_key_validator.py`, `api/registry/api/utils.py`, `api/account/models.py`, `rust-scorer/src/auth/api_key.rs`, `rust-scorer/src/models/django.rs`