# Custom Stamps Frontend Integration and Data Flow

## Overview

The custom stamps feature uses a generic pattern that allows partners to configure custom verification stamps without frontend-specific logic.

## API Response Structure

The endpoint `GET /account/customization/{dashboard_path}/` returns `customStamps` via `Customization.get_custom_stamps()`:

```json
{
  "customStamps": {
    "myPlatformName": {
      "platformType": "DEVEL",
      "iconUrl": "./assets/icon.svg",
      "displayName": "Developer List",
      "description": "Verify developer status",
      "banner": {
        "heading": "...",
        "content": "...",
        "cta": { "text": "...", "url": "..." }
      },
      "isEVM": false,
      "credentials": [
        {
          "providerId": "DeveloperList#MyList#abc1234f",
          "displayName": "My Developer List",
          "description": "..."
        }
      ]
    }
  }
}
```

## Backend Data Models

### CustomPlatform (account/models.py)
- `platform_type`: VARCHAR(5), choices=['DEVEL', 'NFT']
- Fields for display (display_name, icon_url, description, banner_*)
- Internal `name` field (unique)

### CustomCredentialRuleset (account/models.py)
- `credential_type`: VARCHAR(5), mirrors platform_type
- `definition`: JSONField with arbitrary verification rules
- `provider_id`: Auto-generated: `{TypeName}#{definition.name}#{sha256_hash[:8]}`

### CustomCredential (account/models.py)
- Joins CustomPlatform + CustomCredentialRuleset to a Customization
- `weight`: Decimal for scoring this credential

## Provider ID Generation

Deterministic, auto-computed in `CustomCredentialRuleset.save()`:

```python
type_name = [ct.name for ct in CredentialType if ct.value == self.credential_type][0]
definition_hash = sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()[0:8]
self.provider_id = f"{type_name}#{self.name}#{definition_hash}"
```

Example: `credential_type="DEVEL"` → `DeveloperList#MyList#f7e3a1b2`

## Weights Merging

`get_customization_dynamic_weights()` adds custom stamps to scoring:
```python
for custom_credential in self.custom_credentials.all():
    weights[custom_credential.ruleset.provider_id] = str(custom_credential.weight)
```

The Rust scorer receives these merged weights and uses provider_id as dict keys.

## Frontend Consumption Pattern

### Generic Iteration (NOT hardcoded)
1. CustomStamp entries iterated via `Object.entries(customStamps || {})`
2. `platformType` value looked up in `CUSTOM_PLATFORM_TYPE_INFO` registry
3. Unknown platformType throws error: "Unknown custom platform type: {platformType}"
4. Each name generates unique platform ID: `Custom#{platformName}`

### Multiple Platforms of Same Type
Fully supported - each entry's name becomes part of the Custom# ID:
- `{nft1: {platformType: "NFT"}, nft2: {platformType: "NFT"}}` creates `Custom#nft1` and `Custom#nft2`

### platformType Lookup Registry
Location: passport app `config/platformMap.ts`
```typescript
export const CUSTOM_PLATFORM_TYPE_INFO = {
  DEVEL: { basePlatformName: "CustomGithub", platformClass: ..., platformParams: {} },
  // NFT: { basePlatformName: "NFT", platformClass: ..., platformParams: {} }
}
```

### isEVM Determination
- Frontend reads isEVM from base platform specs (not per-custom-stamp)
- `basePlatformSpecs.isEVM` or `platformDefinitions[basePlatformName].PlatformDetails.isEVM`

### Category Organization
- All custom stamps grouped under "{partnerName} Stamps" category
- platformIds: `Object.keys(customStamps).map(name => "Custom#" + name)`

## Credential Definition Endpoint

`GET /account/customization/credential/{provider_id}` returns definition for IAM service:
```json
{
  "ruleset": {
    "name": "MyList",
    "condition": { ... }
  }
}
```

## N+1 Query Issue

`get_custom_stamps()` has N+1 query on `.platform` and `.ruleset` ForeignKeys. Fix: use `select_related('platform', 'ruleset')`.

Same issue in `get_customization_dynamic_weights()`.

See: `api/account/models.py`, `api/account/api.py`, passport app `config/platformMap.ts`, `hooks/usePlatforms.tsx`, `utils/customizationUtils.tsx`
