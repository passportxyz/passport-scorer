# Development Patterns

Reusable patterns, architectural decisions, and code organization conventions.

## LIFO Deduplication Patterns

### Retry Logic for Concurrent Requests

The LIFO deduplication has a retry mechanism with 5 attempts to handle `IntegrityError` exceptions that occur during concurrent requests.

**How it works**:
- When two requests compete to claim the same hash, one will fail with IntegrityError
- This triggers a retry (up to 5 attempts)
- The retry logic is in `account/deduplication/lifo.py:21-36`
- After saving hash links, there's a verification step to ensure the expected number of links were created/updated

### Provider Deduplication in Score Calculation

Only the first stamp per provider contributes weight - subsequent stamps with the same provider get weight=0 and are added to deduped_stamps list. This is critical for correct scoring and matches Python behavior.

**Implementation Details**:
- Provider deduplication occurs during score calculation after LIFO deduplication
- When multiple stamps have the same provider, only the first one gets its full weight
- Subsequent stamps with the same provider are marked with weight=0
- Deduped stamps are tracked in a separate deduped_stamps list
- This ensures fair scoring where users can't inflate scores with multiple stamps from the same provider

See `rust-scorer/src/scoring/calculation.rs`.

## Django Model Patterns

### Enum Choices Don't Require Migrations

When adding new enum choices to Django TextChoices fields, Python-level enum additions do NOT require database schema changes. The choices are handled at the ORM level only.

- Only add a migration if the field definition itself changes (not just the choices tuple)
- Applies to both `CustomPlatform.PlatformType` and `CustomCredentialRuleset.CredentialType`
- Example: Adding `NFTHolder = ("NFT", "NFT Holder")` to existing PlatformType doesn't require a migration
- Adding a new BooleanField like `is_evm` DOES require a migration via AddField operation

**Note**: Django 4.2 may generate an AlterField for choices changes, but this is a no-op at the DB level. See `api/account/models.py`, `api/account/migrations/0035_customcredential_customcredentialruleset_and_more.py`.

### BooleanField AddField with Defaults

When adding new boolean fields to existing models, use AddField with `default=False` or `default=True`. The migration handles backfilling all existing rows.

Example from account app migration 0046:
- `nav_order` (IntegerField default=0)
- `show_in_top_nav` (BooleanField default=False)

Always include `help_text` for admin UI clarity. See `api/account/migrations/0046_add_topnav_dashboard_fields.py`.

### Admin Inline Configuration

Django inline editing for related models uses TabularInline with `extra=0` (no blank rows) and `classes=['collapse']` (hidden by default):

```python
class CustomCredentialInline(admin.TabularInline):
    model = CustomCredential
    extra = 0
```

Add to parent ModelAdmin's `inlines` list. Readonly fields set via `get_readonly_fields()` method. See `api/account/admin.py`.

### JSONField Validation

Use a custom validator function for JSONField that checks required keys and formats:

```python
def validate_custom_stamp_ruleset_definition(value):
    # Check 'name' exists and is alphanumeric
    # Check 'condition' exists
```

Validator is referenced in both model field declaration and clean()/save() methods. This allows flexible definition structures while enforcing minimum schema. Backend doesn't validate type-specific structure - IAM service handles that. See `api/account/models.py`.

## Custom Credential System Architecture

### Evolution History

**Phase 1 (commit 80c97c8, Sep 2024)**:
- `CustomGithubStamp` model with Category TextChoices (repo/org)
- Simple FK to Customization

**Phase 2 (commit 310d718, Sep 2024)**:
- Replaced with generic 3-model framework
- Migration 0035 deleted CustomGithubStamp and created all three new models

### Three-Model Architecture

**1. CustomPlatform**:
- Defines platform metadata (name, icon, display name, description, banner)
- `platform_type`: CharField(max_length=5), choices=['DEVEL', 'NFT']
- Internal `name` field (unique)

**2. CustomCredentialRuleset**:
- Stores arbitrary verification rules in JSONField
- `credential_type`: CharField(max_length=5), mirrors PlatformType enum
- `definition`: JSONField with arbitrary rules
- `provider_id`: Auto-generated from `{type_name}#{definition.name}#{sha256_hash[:8]}`

**3. CustomCredential**:
- Many-to-many join: CustomPlatform + CustomCredentialRuleset → Customization
- `weight`: Decimal for scoring

### Adding New Credential Types

1. Add enum value to BOTH `PlatformType` AND `CredentialType` (they mirror each other)
2. Django 4.2 generates AlterField for choices changes (no-op at DB level)
3. Seed data must manually compute provider_id since RunPython lacks custom save()
4. Provider ID format: `{type_name}#{definition.name}#{sha256(definition)[:8]}`
5. Optional: add model fields like `is_evm` for frontend behavior flags (requires AddField migration)

### Provider ID Generation

```python
type_name = [ct.name for ct in CredentialType if ct.value == self.credential_type][0]
# Gets Python enum member name: "DeveloperList" (not DB value "DEVEL")
definition_hash = sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()[0:8]
self.provider_id = f"{type_name}#{self.name}#{definition_hash}"
```

### Scoring Integration

`get_customization_dynamic_weights()` merges custom credential weights into scorer weights:
```python
for custom_credential in self.custom_credentials.all():
    weights[custom_credential.ruleset.provider_id] = str(custom_credential.weight)
```

See `api/account/models.py`, `api/account/migrations/0035_customcredential_customcredentialruleset_and_more.py`.
