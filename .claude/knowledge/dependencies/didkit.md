# DIDKit Dependency

## Version Information

Python uses `didkit = "*"` (any version) in pyproject.toml. This is used for credential validation through Python FFI.

For Rust implementation, need to verify exact version compatibility. The Python code calls didkit for signature verification with `proofPurpose="assertionMethod"`.

See `api/pyproject.toml`