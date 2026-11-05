# Embed Stamp Customization

Embed product supports customizable stamp sections via EmbedStampSection and EmbedStampSectionItem models.

## Data Models

### EmbedStampSection (`account/models.py`)
- ForeignKey to Customization (dashboard owner)
- title: CharField(max 255) - section heading
- order: IntegerField (lower = first)
- created_at, updated_at timestamps
- Unique constraint: (customization, order)

### EmbedStampSectionItem (`account/models.py`)
- ForeignKey to EmbedStampSection (parent section)
- ForeignKey to PlatformMetadata (stamp reference)
- order: IntegerField (lower = first within section)
- Unique constraint: (section, platform_id)

### PlatformMetadata (`registry/weight_models.py`)
- Replaces hard-coded PLATFORM_CHOICES
- platform_id: CharField(unique) - from stampMetadata.json
- name: CharField - display name
- Populated from external stampMetadata.json via admin action

### StampMetadata (`registry/weight_models.py`)
- Local cache of stamp provider metadata
- provider: CharField(unique, indexed)
- is_beta: BooleanField
- platform: FK to PlatformMetadata (nullable, populated via sync)

## Stamp Metadata Caching

External source: `{PASSPORT_PUBLIC_URL}/stampMetadata.json`

Fetched in `registry/api/v1.py::fetch_all_stamp_metadata()` with Django cache:
- TTL: 1 hour (3600 seconds)
- Cache keys: "metadata" (full list), "metadataByProvider" (provider index)
- Provider-indexed structure: `{provider_name → {name, description, hash, group, platform_info}}`

## API Endpoint

**GET /internal/embed/config?community_id={id}**
- Response: EmbedConfigResponse
- Returns: weights dict + stamp_sections array

```json
{
  "weights": {"provider": "weight_value", ...},
  "stamp_sections": [
    {
      "title": "Section Name",
      "order": 0,
      "items": [{"platform_id": "Provider", "order": 0}]
    }
  ]
}
```

Handler: `handle_get_embed_config()` in `embed/api.py` calls both weights and stamp sections handlers.

Deprecated endpoint: **GET /internal/embed/weights** (returns weights only, use /config instead)

## Data Flow

1. Frontend calls GET /internal/embed/config?community_id={id}
2. Handler finds Community → Customization relationship
3. Load EmbedStampSection records ordered by order field
4. For each section, load EmbedStampSectionItem records
5. Return combined weights + stamp_sections
6. Stamp isBeta metadata fetched from StampMetadata table

## Admin Interface

- EmbedStampSectionItemInline: TabularInline for editing items
- EmbedStampSectionInline: StackedInline for sections
- EmbedStampSectionAdmin: Standalone admin with list/filter/search
- CustomizationAdmin: Includes collapsible "Embed Stamp Sections" fieldset

## Performance Note

N+1 query issue: `get_custom_stamps()` and `get_customization_dynamic_weights()` need `select_related('platform', 'ruleset')` to avoid multiple queries per item.

Migration: `api/account/migrations/0048_add_embed_stamp_section_models.py`
