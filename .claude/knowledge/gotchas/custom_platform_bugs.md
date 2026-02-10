# Custom Platform Bugs

## [2026-02-10] CustomPlatformAdmin search_display bug

The `CustomPlatformAdmin` class in `api/account/admin.py` has `search_display` instead of `search_fields`. This is a silent bug introduced in commit 310d718 (feat(api): adding custom stamp framework, Sep 16 2024, PR #673). Django ignores `search_display` as it is not a recognized ModelAdmin attribute, meaning admin search for CustomPlatform has been broken since introduction (~17 months). The adjacent `CustomCredentialRulesetAdmin` correctly uses `search_fields`.

See: `api/account/admin.py`

## [2026-02-10] CustomPlatform.is_evm hardcoded False in API

The `get_custom_stamps()` method hardcodes `'isEVM': False` on all platforms. When adding the `is_evm` BooleanField to CustomPlatform, this line must be updated to use `platform.is_evm` instead. This is critical for NFT stamps which require `isEVM=True` to signal the frontend that on-chain verification is needed.

See: `api/account/models.py`
