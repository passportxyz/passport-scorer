# Embed Stamp Customization Architecture

## Overview

The Embed product supports customizable stamp sections, allowing partners to organize and display stamps in customized sections through the Customization model.

## Key Models

### EmbedStampSection (account/models.py)
- **Purpose**: Defines sections that contain related stamps for Embed UI
- **Fields**:
  - `customization` (ForeignKey to Customization) - which partner/dashboard owns this section
  - `title` (CharField, max 255) - section title e.g., "Physical Verification", "Web2 Platforms"
  - `order` (IntegerField, default 0) - display order (lower = first)
  - `created_at`, `updated_at` - timestamps
- **Meta**: Ordered by order/id, unique constraint on (customization, order)
- **Relation**: Has many EmbedStampSectionItem via related_name="items"

### EmbedStampSectionItem (account/models.py)
- **Purpose**: Individual stamps within a section
- **Fields**:
  - `section` (ForeignKey to EmbedStampSection) - which section contains this stamp
  - `platform` (ForeignKey to PlatformMetadata) - the stamp/platform reference
  - `order` (IntegerField, default 0) - display order within section
  - `created_at`, `updated_at` - timestamps
- **Meta**: Ordered by order/id, unique constraint on (section, platform_id)

### PlatformMetadata (registry/weight_models.py)
- **Purpose**: Replaces hard-coded PLATFORM_CHOICES, stores platform metadata from external stampMetadata.json
- **Fields**:
  - `platform_id` (CharField, unique) - from stampMetadata.json
  - `name` (CharField) - display name
- **Relations**: StampMetadata has nullable FK to PlatformMetadata
- **Admin**: Has "Sync from Stamp Metadata" button that fetches external stampMetadata.json and upserts platforms

### StampMetadata (registry/weight_models.py)
- **Purpose**: Local database model for stamp provider metadata
- **Fields**:
  - `provider` (CharField, max 100, unique, indexed) - provider name
  - `is_beta` (BooleanField) - whether stamp has beta badge
  - `platform` (FK to PlatformMetadata, nullable) - linked via sync
- **Phase 2 TODO**: Will become source of truth for all stamp providers

## Stamp Metadata Caching

### External Source
- Fetched from passport repo via HTTP: `{PASSPORT_PUBLIC_URL}/stampMetadata.json`
- `fetch_all_stamp_metadata()` in registry/api/v1.py
- Django cache with 1-hour TTL (3600 seconds)
- Cache keys: "metadata" (full list), "metadataByProvider" (indexed by provider)

### Provider Indexing
- `fetch_stamp_metadata_for_provider()` builds provider-indexed cache
- Structure: `{provider_name → {name, description, hash, group, platform_info}}`

## API Endpoints

### GET /internal/embed/config
- **Response**: EmbedConfigResponse (embed/api.py)
- **Returns**:
  ```json
  {
    "weights": {"provider_name": "weight_value", ...},
    "stamp_sections": [
      {
        "title": "Section Name",
        "order": 0,
        "items": [{"platform_id": "Provider", "order": 0}]
      }
    ]
  }
  ```
- **Handler**: `handle_get_embed_config()` calls both weights and stamp sections handlers

### GET /internal/embed/weights (DEPRECATED)
- Still works but redirected to /embed/config
- Returns only weights dict

## Data Flow

1. Frontend calls `GET /internal/embed/config?community_id={id}`
2. Handler finds Community → Customization relationship
3. Loads EmbedStampSection records ordered by order field
4. For each section, loads EmbedStampSectionItem records
5. Returns combined response with weights + stamp_sections
6. Stamp metadata (isBeta flags) fetched separately from local database

## Admin Configuration

- **EmbedStampSectionItemInline**: TabularInline for editing items within a section
- **EmbedStampSectionInline**: StackedInline for editing sections within customization
- **EmbedStampSectionAdmin**: Standalone admin with list_display, list_filter, search_fields
- **CustomizationAdmin**: Includes "Embed Stamp Sections" fieldset (collapsed)

See: `api/account/models.py`, `api/account/admin.py`, `api/embed/api.py`, `api/internal/api.py`, `api/registry/weight_models.py`, `api/account/migrations/0048_add_embed_stamp_section_models.py`
