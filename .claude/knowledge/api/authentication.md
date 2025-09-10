# API Authentication

## API Key Authentication Mechanism

API keys use djangorestframework-api-key (v2) with AbstractAPIKey model.

### Key Storage Structure:
- **Prefix**: First 8 chars for lookup
- **Hashed key**: SHA512 hash for security
- **Permissions**: 
  - submit_passports
  - read_scores
  - create_scorers
  - historical_endpoint
- **Rate limits**: Separate for standard, analysis, and embed endpoints
- **Analytics tracking**: Via AccountAPIKeyAnalytics table

### Hashing Scheme (djangorestframework-api-key v2):
- **Key format**: prefix.secret_key
- **Prefix**: First 8 chars of the key for DB lookup
- **Full key**: Hashed with SHA512 and stored as "sha512$$<hex_hash>"
- **Validation**: The is_valid() method on the model validates the full key against the hash
- **Security**: Uses constant-time comparison to prevent timing attacks

### Authentication Flow:
1. Check X-API-Key header first, then Authorization header
2. Look up by prefix, verify against hashed_key
3. Attach to request.api_key for usage tracking
4. Special handling for DEMO_API_KEY_ALIASES
5. Must have read_scores permission for scoring endpoint

### Database Tables:
- **account_accountapikey**: API key storage with permissions (inherits from AbstractAPIKey)
- **account_accountapikeyanalytics**: Usage tracking with paths, payloads, responses

### Rust Implementation:
- Exact SHA512 hashing matching Python implementation
- Verified with test: Python and Rust produce identical hashes
- Demo key aliases support via environment variable
- API usage tracking to AccountAPIKeyAnalytics table

See `api/registry/api/utils.py`, `api/account/models.py`, `rust-scorer/src/auth/api_key.rs`