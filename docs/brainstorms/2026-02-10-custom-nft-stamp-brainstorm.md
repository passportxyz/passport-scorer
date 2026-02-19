---
date: 2026-02-10
topic: custom-nft-stamp
---

# Custom NFT Stamp

## What We're Building

Add a new custom credential type for NFT ownership verification. Partners can configure stamps that award points to users who hold specific NFTs across any EVM chain. This builds on the existing `CustomPlatform` / `CustomCredentialRuleset` / `CustomCredential` system, adding a new `NFT` type alongside the existing `DEVEL` (Developer List) type.

The backend stores the NFT rule definitions and serves them via the existing API. The IAM service (separate repo) reads these definitions and performs the actual on-chain verification. The frontend (separate repo) consumes the same `customStamps` response structure already used for developer list stamps.

## Why This Approach

We evaluated adding NFT stamps as a completely new system vs. extending the existing custom credential framework. Extending is clearly the right call:

- The `CustomCredentialRuleset.definition` JSONField already stores arbitrary verification rules
- The `get_customization_dynamic_weights()` method already merges custom weights into scoring
- The `get_custom_stamps()` method already builds the API response for the frontend
- The provider_id auto-generation (`{Type}#{Name}#{Hash}`) handles uniqueness
- The admin interface already has inline editing for custom credentials

The only additions needed are: a new enum value, one new model field, and a migration.

## Key Decisions

### 1. Type Naming: `NFTHolder`

Following the existing convention:

| | Developer List (existing) | NFT Holder (new) |
|---|---|---|
| DB value | `"DEVEL"` | `"NFT"` |
| Enum attribute | `DeveloperList` | `NFTHolder` |
| Display label | `"Developer List"` | `"NFT Holder"` |
| Provider ID prefix | `DeveloperList#...` | `NFTHolder#...` |

Example provider_id: `NFTHolder#BoredApes#f7e3a1b2`

The `max_length=5` constraint on both `platform_type` and `credential_type` fields accommodates `"NFT"` (3 chars).

### 2. `is_evm` Field on CustomPlatform

Add a `BooleanField` `is_evm` to `CustomPlatform` (default `False`). This replaces the hardcoded `"isEVM": False` in `get_custom_stamps()` (line 676 of `account/models.py`).

- Developer List platforms: `is_evm = False`
- NFT Holder platforms: `is_evm = True`

The frontend uses this to determine the verification flow (on-chain vs. off-chain).

### 3. Definition Structure: Flexible Multi-Contract

The `condition` JSON supports an array of contracts, allowing a single stamp to verify ownership across multiple chains/collections:

```json
{
  "name": "BoredApes",
  "condition": {
    "contracts": [
      {
        "address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        "chainId": 1,
        "standard": "ERC-721"
      },
      {
        "address": "0x1234...abcd",
        "chainId": 8453,
        "standard": "ERC-721"
      }
    ]
  }
}
```

Key fields per contract entry:
- `address`: Contract address (hex string)
- `chainId`: Chain ID (integer)
- `standard`: Token standard as free string (e.g., `"ERC-721"`, `"ERC-1155"`, `"ERC-20"`)

Verification logic: user holds **at least 1 token** from **any** of the listed contracts.

### 4. Standard-Agnostic

The `standard` field is a free string validated by the IAM service, not the backend. This keeps the backend decoupled from on-chain verification specifics and avoids needing backend changes when new token standards emerge.

### 5. Verification Depth: Ownership Only

Just balance >= 1 for now. No `minBalance`, no `tokenIds` filtering. Keeps the initial implementation simple. Additional fields can be added to the condition JSON later without breaking existing stamps.

### 6. Backend Validation: Keep Generic

The existing `validate_custom_stamp_ruleset_definition()` validator only checks for `name` (alphanumeric) and `condition` (present). No NFT-specific validation added to the backend. The IAM service validates the condition structure when it processes verification requests. Admin errors are caught at verification time.

## Concrete Changes Required

### Model Changes (`api/account/models.py`)

1. Add `NFTHolder = ("NFT", "NFT Holder")` to both:
   - `CustomPlatform.PlatformType` choices
   - `CustomCredentialRuleset.CredentialType` choices

2. Add `is_evm` BooleanField to `CustomPlatform`:
   ```python
   is_evm = models.BooleanField(default=False, help_text="Whether this platform requires EVM verification")
   ```

3. Update `get_custom_stamps()` to use `platform.is_evm` instead of hardcoded `False`

### Migration

One migration covering:
- New `is_evm` field on `CustomPlatform` (default False, non-breaking)
- Enum choices are just Python-level, no DB migration needed for those

### Admin Changes (`api/account/admin.py`)

- Add `is_evm` to `CustomPlatformAdmin` list_display and fieldsets
- No other admin changes needed (existing inline editors work for NFT credentials)

### Rust Scorer Impact

None. The Rust scorer reads weights as a string->decimal dict from `get_customization_dynamic_weights()`. NFT stamp provider IDs like `NFTHolder#BoredApes#f7e3a1b2` are just new keys in that dict. Scoring works automatically.

### API Response Impact

The existing `/account/customization/{path}/` response includes `customStamps` via `get_custom_stamps()`. NFT stamps will appear in the same structure:

```json
{
  "customStamps": {
    "myNFTPlatform": {
      "platformType": "NFT",
      "iconUrl": "./assets/nft-icon.svg",
      "displayName": "NFT Collection",
      "description": "Verify NFT ownership",
      "banner": { ... },
      "isEVM": true,
      "credentials": [
        {
          "providerId": "NFTHolder#BoredApes#f7e3a1b2",
          "displayName": "Bored Ape Yacht Club",
          "description": "Holders of BAYC NFTs"
        }
      ]
    }
  }
}
```

The frontend repo distinguishes NFT stamps from developer list stamps via `platformType: "NFT"` and `isEVM: true`.

### Credential Definition Endpoint

The existing `GET /account/customization/credential/{provider_id}` endpoint works unchanged. When the IAM service requests the definition for an NFT stamp, it gets:

```json
{
  "ruleset": {
    "name": "BoredApes",
    "condition": {
      "contracts": [
        {"address": "0xBC4CA0...", "chainId": 1, "standard": "ERC-721"}
      ]
    }
  }
}
```

The IAM uses this to perform the on-chain `balanceOf` check.

## What's Out of Scope

- **Embed stamp sections** (handled in separate ticket - new stamps just need to be added to sections via admin)
- **IAM on-chain verification logic** (separate repo)
- **Frontend UI for NFT stamps** (separate repo, consumes the API response above)
- **Token ID filtering, minimum balance, trait checks** (can be added to condition later)

## Seeding

Seed one example NFT stamp configuration in the migration to serve as a reference for admins configuring future stamps. (Specific collection TBD - pick something well-known like a partner's existing NFT.)

## Next Steps

--> `/workflows:plan` for implementation details
