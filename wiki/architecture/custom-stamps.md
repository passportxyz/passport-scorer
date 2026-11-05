# Custom Stamps Architecture

Generic framework for partners to configure custom verification stamps without frontend hardcoding.

## Three-Model Framework

### CustomPlatform (`account/models.py`)
- platform_type: CharField(max 5), choices=['DEVEL', 'NFT']
- display_name, icon_url, description, banner_* fields
- Internal name field (unique)

### CustomCredentialRuleset (`account/models.py`)
- credential_type: CharField(max 5), mirrors PlatformType enum
- definition: JSONField with arbitrary verification rules
- provider_id: Auto-generated as `{TypeName}#{definition.name}#{sha256_hash[:8]}`

### CustomCredential (`account/models.py`)
- Joins CustomPlatform + CustomCredentialRuleset to a Customization
- weight: Decimal for scoring

## Provider ID Generation

Deterministic, computed in `CustomCredentialRuleset.save()`:

```python
type_name = [ct.name for ct in CredentialType if ct.value == self.credential_type][0]
definition_hash = sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()[0:8]
self.provider_id = f"{type_name}#{self.name}#{definition_hash}"
```

Example: credential_type="DEVEL" → `DeveloperList#MyList#f7e3a1b2`

## API Response

**GET /account/customization/{dashboard_path}/** returns:

```json
{
  "customStamps": {
    "myPlatformName": {
      "platformType": "DEVEL",
      "iconUrl": "./assets/icon.svg",
      "displayName": "Developer List",
      "description": "...",
      "banner": {"heading": "...", "content": "...", "cta": {...}},
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

Via `Customization.get_custom_stamps()` method.

## Frontend Consumption

Generic iteration pattern (NOT hardcoded):
1. Iterate `Object.entries(customStamps || {})`
2. Look up platformType in `CUSTOM_PLATFORM_TYPE_INFO` registry (passport app `config/platformMap.ts`)
3. Each custom stamp generates platform ID: `Custom#{platformName}`
4. Unknown platformType throws error

Multiple platforms of same type supported:
- `{nft1: {platformType: "NFT"}, nft2: {platformType: "NFT"}}` creates `Custom#nft1` and `Custom#nft2`

isEVM determination from base platform specs, not per-stamp.

All custom stamps grouped under `{partnerName} Stamps` category.

## Weights Integration

`Customization.get_customization_dynamic_weights()` merges custom credential weights into scorer weights:

```python
for custom_credential in self.custom_credentials.all():
    weights[custom_credential.ruleset.provider_id] = str(custom_credential.weight)
```

Rust scorer receives merged weights and uses provider_id as dict keys.

## Credential Definition Endpoint

**GET /internal/customization/credential/{provider_id}** returns:

```json
{
  "ruleset": {
    "name": "MyList",
    "condition": { ... }
  }
}
```

Used by IAM service for verification logic.

## Adding New Credential Types

1. Add enum value to BOTH `PlatformType` AND `CredentialType` (they mirror)
2. Django 4.2 generates AlterField (no-op at DB)
3. Manually compute provider_id for seed data
4. Optional: Add model fields like is_evm (requires AddField migration)

Migration: `api/account/migrations/0035_customcredential_customcredentialruleset_and_more.py`

## Performance Note

N+1 query issue: `get_custom_stamps()` and `get_customization_dynamic_weights()` need `select_related('platform', 'ruleset')`.

Model: `api/account/models.py`
API: `api/account/api.py`
