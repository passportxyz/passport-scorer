# API Key Hashing Performance Issue

## [2025-10-16] API Key PBKDF2 Performance Problem

The API key validation takes 2.5 seconds because it's using Django's password hashing (pbkdf2_sha256 with 600,000 iterations) instead of a simple fast hash like SHA-256/512. This is inappropriate for API keys which already have high entropy and don't need protection against dictionary attacks.

### The Problem

API keys should use:
- Simple SHA-256/512 (microseconds) instead of PBKDF2 (seconds)
- API keys have high entropy (32+ random bytes), unlike passwords
- The threat model is different - API keys aren't vulnerable to dictionary attacks

The djangorestframework-api-key v2 library normally uses SHA512, but somehow the implementation is using Django's password hasher instead. This causes massive unnecessary latency on every API request.

**Important**: Increasing Lambda size won't help - PBKDF2 is intentionally CPU-hard by design.

See `api/account/models.py`, `rust-scorer/src/auth/api_key.rs`