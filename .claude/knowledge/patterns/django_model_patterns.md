# Django Model Patterns

## Enum Choices Don't Require Migrations

When adding new enum choices to Django TextChoices fields, Python-level enum additions do NOT require database schema changes. The choices are handled at the ORM level only.

- Only add a migration if the field definition itself changes (not just the choices tuple)
- Applies to both `CustomPlatform.PlatformType` and `CustomCredentialRuleset.CredentialType`
- Example: Adding `NFTHolder = ("NFT", "NFT Holder")` to existing PlatformType doesn't require a migration
- Adding a new BooleanField like `is_evm` DOES require a migration via AddField operation

**Note**: Django 4.2 may generate an AlterField for choices changes, but this is a no-op at the DB level.

See: `api/account/models.py`, `api/account/migrations/0035_customcredential_customcredentialruleset_and_more.py`

## BooleanField AddField with Defaults

When adding new boolean fields to existing models, use AddField with `default=False` or `default=True`. The migration handles backfilling all existing rows.

Example from account app migration 0046:
- `nav_order` (IntegerField default=0)
- `show_in_top_nav` (BooleanField default=False)

Always include `help_text` for admin UI clarity.

See: `api/account/migrations/0046_add_topnav_dashboard_fields.py`

## Admin Inline Configuration

Django inline editing for related models uses TabularInline with `extra=0` (no blank rows) and `classes=['collapse']` (hidden by default):

```python
class CustomCredentialInline(admin.TabularInline):
    model = CustomCredential
    extra = 0
```

Add to parent ModelAdmin's `inlines` list. Readonly fields set via `get_readonly_fields()` method.

See: `api/account/admin.py`

## JSONField Validation

Use a custom validator function for JSONField that checks required keys and formats:

```python
def validate_custom_stamp_ruleset_definition(value):
    # Check 'name' exists and is alphanumeric
    # Check 'condition' exists
```

Validator is referenced in both model field declaration and clean()/save() methods. This allows flexible definition structures while enforcing minimum schema. Backend doesn't validate type-specific structure - IAM service handles that.

See: `api/account/models.py`
