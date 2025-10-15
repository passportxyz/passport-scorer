# TRUSTED_IAM_ISSUERS Environment Variable

## [2025-10-15] Environment Variable Configuration

The Rust scorer correctly loads TRUSTED_IAM_ISSUERS from the environment variable (as a JSON array) instead of using hardcoded values, matching the Python implementation.

### Implementation Details

- Uses OnceLock for lazy initialization and caching
- Fallback to default values if the env var is not set or fails to parse
- Defaults match Python's settings.base.py defaults

### Format

```bash
TRUSTED_IAM_ISSUERS='["did:key:...", "did:ethr:0x..."]'
```

This ensures the Rust implementation maintains parity with Python's dynamic configuration approach rather than hardcoding IAM issuer values.

See `rust-scorer/src/auth/credentials.rs`, `api/scorer/settings/base.py`
