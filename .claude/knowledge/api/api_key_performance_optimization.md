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

### Implementation Files

- `api/account/api_key_validator.py` - FastAPIKeyValidator class implementation
- `api/registry/api/utils.py` - Integration with API authentication flow
- `api/account/models.py` - AccountAPIKey model with new field
- `api/account/migrations/0044_add_hashed_key_sha256.py` - Database migration

See `api/account/api_key_validator.py`, `api/registry/api/utils.py`, `api/account/models.py`