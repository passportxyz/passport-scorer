# Custom Credential System Pattern

## Evolution History

### Phase 1 (commit 80c97c8, Sep 2024)
- `CustomGithubStamp` model with Category TextChoices (repo/org)
- Simple FK to Customization

### Phase 2 (commit 310d718, Sep 2024)
- Replaced with generic 3-model framework
- Migration 0035 deleted CustomGithubStamp and created all three new models

## Three-Model Architecture

### 1. CustomPlatform
- Defines platform metadata (name, icon, display name, description, banner)
- `platform_type`: CharField(max_length=5), choices=['DEVEL', 'NFT']
- Internal `name` field (unique)

### 2. CustomCredentialRuleset
- Stores arbitrary verification rules in JSONField
- `credential_type`: CharField(max_length=5), mirrors PlatformType enum
- `definition`: JSONField with arbitrary rules
- `provider_id`: Auto-generated from `{type_name}#{definition.name}#{sha256_hash[:8]}`

### 3. CustomCredential
- Many-to-many join: CustomPlatform + CustomCredentialRuleset → Customization
- `weight`: Decimal for scoring

## Adding New Credential Types

1. Add enum value to BOTH `PlatformType` AND `CredentialType` (they mirror each other)
2. Django 4.2 generates AlterField for choices changes (no-op at DB level)
3. Seed data must manually compute provider_id since RunPython lacks custom save()
4. Provider ID format: `{type_name}#{definition.name}#{sha256(definition)[:8]}`
5. Optional: add model fields like `is_evm` for frontend behavior flags (requires AddField migration)

## Provider ID Generation

```python
type_name = [ct.name for ct in CredentialType if ct.value == self.credential_type][0]
# Gets Python enum member name: "DeveloperList" (not DB value "DEVEL")
definition_hash = sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()[0:8]
self.provider_id = f"{type_name}#{self.name}#{definition_hash}"
```

## Scoring Integration

`get_customization_dynamic_weights()` merges custom credential weights into scorer weights:
```python
for custom_credential in self.custom_credentials.all():
    weights[custom_credential.ruleset.provider_id] = str(custom_credential.weight)
```

See: `api/account/models.py`, `api/account/migrations/0035_customcredential_customcredentialruleset_and_more.py`
