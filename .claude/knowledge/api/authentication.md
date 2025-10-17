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

### Hashing Scheme:
- **Key format**: prefix.secret_key
- **Prefix**: First 8 chars of the key for DB lookup
- **Full key**: Uses Django's default password hashing (pbkdf2_sha256$600000$...) format, NOT sha512$$ format
- **Validation**: The is_valid() method on the model validates the full key against the hash
- **Security**: Uses constant-time comparison to prevent timing attacks
- **Important**: The API keys use Django's built-in password hashing, not djangorestframework-api-key v2's SHA512 format

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
- Must implement PBKDF2-SHA256 verification to match Django's password hashing
- Demo key aliases support via environment variable
- API usage tracking to AccountAPIKeyAnalytics table
- Field types: id is VARCHAR(150), account_id is BIGINT (i64)

See `api/registry/api/utils.py`, `api/account/models.py`, `rust-scorer/src/auth/api_key.rs`