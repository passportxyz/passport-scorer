### [19:44] [dependency] Valkey/Redis requirement for dev setup
**Details**: Django's caching system requires Redis/Valkey to be running for the development environment. The CACHES setting in api/scorer/settings/base.py uses django.core.cache.backends.redis.RedisCache with location from CELERY_BROKER_URL (defaults to redis://localhost:6379/0).

The docker-compose.yml includes a Redis service, but the local dev setup script (dev-setup/setup.sh) was missing Redis/Valkey installation and startup.

Added to dev setup:
- Install valkey or redis package via dnf (Valkey is the Redis fork that Fedora is adopting)
- Start server with: valkey-server --daemonize yes --bind 127.0.0.1 --port 6379
- Add CELERY_BROKER_URL=redis://localhost:6379/0 to .env.development
- Created start-redis.sh helper script for restarting the service

The setup works in container environments without systemctl - just uses the binary directly with --daemonize flag.
**Files**: dev-setup/setup.sh, dev-setup/install.sh, dev-setup/start-redis.sh, api/scorer/settings/base.py, docker-compose.yml
---

### [17:14] [architecture] Branch 3472: Embed Stamp Customization Architecture
**Details**: ## Branch Overview
The 3472-embed-stamp-customization branch adds customizable stamp sections for the Embed product, allowing partners to organize and display stamps in customized sections.

## Key Models Added

### 1. EmbedStampSection (account/models.py lines 856-887)
- **Purpose**: Defines sections that contain related stamps for Embed UI
- **Fields**:
  - `customization` (ForeignKey to Customization) - which partner/dashboard owns this section
  - `title` (CharField, max 255) - section title e.g., "Physical Verification", "Web2 Platforms"
  - `order` (IntegerField, default 0) - display order (lower = first)
  - `created_at`, `updated_at` - timestamps
- **Meta**: Ordered by order/id, unique constraint on (customization, order)
- **Relation**: Has many EmbedStampSectionItem via related_name="items"

### 2. EmbedStampSectionItem (account/models.py lines 889-937)
- **Purpose**: Individual stamps within a section
- **Hard-coded PLATFORM_CHOICES** (lines 896-909):
  - Physical Verification: Binance, Biometrics, Coinbase, HumanIdKyc, CleanHands, HumanIdPhone
  - Web2 Platforms: Discord, Github, Google, Linkedin
- **Fields**:
  - `section` (ForeignKey to EmbedStampSection) - which section contains this stamp
  - `platform_id` (CharField, max 100, choices=PLATFORM_CHOICES) - the stamp/platform identifier
  - `order` (IntegerField, default 0) - display order within section
  - `created_at`, `updated_at` - timestamps
- **Meta**: Ordered by order/id, unique constraint on (section, platform_id)

## Stamp Metadata Caching Architecture

### How Stamp Metadata is Fetched (registry/api/v1.py)
1. **Source**: Fetched from passport repo via HTTP
   - `METADATA_URL = urljoin(settings.PASSPORT_PUBLIC_URL, "stampMetadata.json")`
   - `PASSPORT_PUBLIC_URL` from settings, defaults to "http://localhost:80"
   - Actual URL: `{PASSPORT_PUBLIC_URL}/stampMetadata.json`

2. **Caching Strategy**:
   - Function: `fetch_all_stamp_metadata()` (lines 626-659)
   - Uses Django cache with 1-hour TTL (3600 seconds)
   - Cache keys: "metadata" (full list), "metadataByProvider" (indexed by provider)

3. **Data Structure**:
   - Response contains StampDisplayResponse objects
   - Each platform has groups, each group has stamps
   - Icons are relative URLs, joined with PASSPORT_PUBLIC_URL base

4. **Provider Indexing**:
   - `fetch_stamp_metadata_for_provider()` builds provider-indexed cache
   - Cache structure: {provider_name → {name, description, hash, group, platform_info}}

### StampMetadata Local Model (registry/weight_models.py lines 7-47)
- **Purpose**: Local database model for stamp provider metadata
- **Fields**:
  - `provider` (CharField, max 100, unique, indexed) - provider name
  - `is_beta` (BooleanField) - whether stamp has beta badge
- **Method**: `get_all_metadata_dict()` returns {provider → {isBeta: bool}}
- **Note**: Phase 2 TODO - will become source of truth for all stamp providers

## API Endpoints for Configuration

### GET /internal/embed/config (internal/api.py lines 144-154)
- **Response**: EmbedConfigResponse (embed/api.py lines 133-137)
- **Returns**:
  ```json
  {
    "weights": {provider_name: weight_value, ...},
    "stamp_sections": [
      {
        "title": "Section Name",
        "order": 0,
        "items": [
          {"platform_id": "Provider", "order": 0},
          ...
        ]
      }
    ]
  }
  ```
- **Handler**: `handle_get_embed_config()` (embed/api.py lines 185-195)
  - Calls `handle_get_scorer_weights()` for weights
  - Calls `handle_get_embed_stamp_sections()` for stamp sections

### GET /internal/embed/weights (DEPRECATED)
- Still works but redirects to /embed/config
- Returns only weights dict

### GET /internal/embed/score/{scorer_id}/{address}
- Returns score with stamps for address

## Admin Configuration

### EmbedStampSectionItemInline (account/admin.py lines 704-709)
- TabularInline for editing items within a section
- Fields: platform_id, order
- Extra 1 item for adding new stamps

### EmbedStampSectionInline (account/admin.py lines 712-718)
- StackedInline for editing sections within customization
- Fields: title, order
- show_change_link allows direct editing of full section details

### EmbedStampSectionAdmin (account/admin.py lines 721-742)
- Standalone admin for managing sections
- list_display: id, customization, title, order, item_count, created_at
- list_filter: customization
- search_fields: title, customization__path
- inlines: [EmbedStampSectionItemInline]
- Custom item_count method shows # items

### CustomizationAdmin Updates (account/admin.py lines 744-789)
- Added "Embed Stamp Sections" fieldset (collapsed, descriptive)
- Added EmbedStampSectionInline to inlines list
- Organized with TopNav Configuration fieldset

## Data Flow for Embed Configuration

1. Frontend calls `GET /internal/embed/config?community_id={id}`
2. Handler finds Community → Customization relationship
3. Loads EmbedStampSection records ordered by order field
4. For each section, loads EmbedStampSectionItem records
5. Returns combined response with weights (from WeightConfiguration) + stamp_sections
6. Stamp metadata (isBeta flags) fetched separately from local database

## Recent Commits on Branch
- 7da24a3: Combine weights and stamp sections into /embed/config endpoint
- 453fd6d: Add weight configuration setup for embed stamp sections tests
- 859b232: Create test user for account setup in embed stamp sections tests
- 616ffae: Update import for deletion in embed stamp section models
- f6a1a6e: Add customizable stamp sections for partners
**Files**: api/account/models.py (lines 856-937), api/account/admin.py (lines 704-752), api/embed/api.py (lines 120-196), api/internal/api.py (lines 144-154), api/registry/weight_models.py (lines 7-47), api/account/migrations/0048_add_embed_stamp_section_models.py
---

### [17:46] [architecture] PlatformMetadata model for embed stamp sections
**Details**: PlatformMetadata model in registry/weight_models.py replaces the hard-coded PLATFORM_CHOICES on EmbedStampSectionItem. It has platform_id (unique, from stampMetadata.json) and name fields. StampMetadata has a nullable FK to PlatformMetadata. EmbedStampSectionItem now uses a FK to PlatformMetadata instead of a CharField. The PlatformMetadataAdmin has a "Sync from Stamp Metadata" button that fetches external stampMetadata.json via fetch_all_stamp_metadata() and upserts platforms + links StampMetadata records. The API (embed/api.py) reads item.platform.platform_id to keep the same string response format.
**Files**: api/registry/weight_models.py, api/account/models.py, api/registry/admin.py, api/embed/api.py
---

### [20:17] [architecture] Custom Stamps Backend Integration Architecture
**Details**: ## Baseline Overview (Main Branch)

The custom stamps feature enables the embed service and frontend to display guest list (AllowList) and developer list (DeveloperList) stamps.

### Python Scorer Backend (api/embed/api.py)

**New Endpoint**: `GET /internal/embed/config?community_id={community_id}`

Returns `EmbedConfigResponse`:
```python
{
  "weights": dict[str, float],  # All stamp weights
  "stamp_sections": List[EmbedStampSectionSchema]  # Custom section ordering
}
```

**Schema Types**:
- `EmbedStampSectionSchema`: Contains title, order, and list of platform_id items
- `EmbedStampSectionItemSchema`: Simple platform_id + order
- `EmbedConfigResponse`: Combined weights and sections

**Implementation Functions**:
- `handle_get_embed_config(community_id)`: Main handler, combines weights + sections
- `handle_get_embed_stamp_sections(community_id)`: Queries Customization, EmbedSectionOrder, EmbedStampPlatform tables
- Returns empty list if Customization doesn't exist or tables don't have data

**Data Model Requirements**:
- Customization model (existing)
- EmbedSectionOrder model: links customization → section with order field
- EmbedStampPlatform model: links customization → platform with section + order
- Tables ordered by: order field, then id (for stability)

### TypeScript Embed Frontend (embed/src/metadata.ts)

**Three Data Formats Supported** (in order of preference):

1. **New Unified Format** (`configData.platforms` present):
   - Single `platforms` array with complete platform definitions
   - Includes icon_platform_id (for looking up icon), name, description, documentation_link, requires_* flags, credentials
   - Preferred when available; makes custom_stamps completely optional
   - Frontend resolves section structure from `stamp_sections`

2. **Deprecated Custom Stamps Format** (backward compat, used if platforms not present):
   - Separate `allow_list_stamps` and `developer_list_stamps` arrays
   - Each stamp has: provider_id, display_name, description, weight
   - Frontend creates "Guest List" and "Developer List" sections automatically
   - Still functional but moving away from this

3. **Standard Sections** (fallback when sections empty):
   - Uses `STAMP_PAGES` from client-side stamps.ts
   - No custom ordering or filtering

**New Mock Data in Tests**:
- Added platforms like `AllowList` and `DeveloperList` with PlatformDetails.icon
- Response includes `platforms` array, `custom_stamps` section, or both
- Tests verify preference: platforms field takes precedence over custom_stamps

### Test Coverage Changes

**Added Tests** (PR):
1. "should include Guest List and Developer List sections when custom_stamps is present" - legacy format
2. "should handle unified platforms array format" - new format with all platform fields
3. "should support multiple custom platforms in same section" - new format with ordering
4. "should prefer platforms field over custom_stamps when both present" - precedence
5. "should fall back to default STAMP_PAGES when stamp_sections is empty" - fallback

**Baseline Tests** (still present):
- Missing scorerId validation (400 error)
- Basic metadata structure and filtering
- Custom stamp sections with ordering
- Error handling (500 on fetch failure)

### Frontend Response Transformation

The metadataHandler:
1. Fetches config from `/internal/embed/config?community_id={scorerId}`
2. If `platforms` field present: Build sections from `stamp_sections` + resolve each platform reference
   - For custom platforms: Use PlatformDefinition data directly
   - For standard platforms: Merge static STAMP_PAGES data with passport-platforms data
3. If `platforms` not present: Use deprecated custom_stamps format (automatic "Guest List" + "Developer List" sections)
4. Always falls back to STAMP_PAGES if stamp_sections empty
5. Filters platforms: removes any with displayWeight = 0

**Key Types in Response**:
```typescript
{
  header: string;
  platforms: Array<{
    platformId: string;
    name: string;
    description: string;
    documentationLink: string;
    requiresSignature?: boolean;
    requiresPopup?: boolean;
    popupUrl?: string;
    requiresSDKFlow?: boolean;
    icon: string;  // SVG content or URL
    credentials: Array<{ id: string; weight: string }>;
    displayWeight: string;  // formatted decimal
  }>;
}[]
```

### Platform Definitions

**Custom Platforms** (AllowList, DeveloperList):
- platform_id: Full identifier (e.g., "AllowList#VIPList")
- icon_platform_id: Maps to passport-platforms entry (e.g., "AllowList")
- Credentials come from configData.platforms directly

**Standard Platforms** (Binance, Google, etc.):
- platform_id: Key in passport-platforms
- Credentials come from passport-platforms[platformId].providers
- Weights looked up from configData.weights by provider type

### Mock Structure

Tests mock passport-platforms with:
```javascript
{
  AllowList: { PlatformDetails: { icon: "./assets/star-light.svg" }, providers: [] },
  CustomGithub: { PlatformDetails: { icon: "./assets/dev-icon.svg" }, providers: [] },
  Binance: { PlatformDetails: { icon: "./assets/binanceStampIcon.svg" }, providers: [...] }
}
```

Empty providers arrays for custom platforms, real providers for standard platforms.

## Integration Points

1. **Scorer → Frontend**: Config endpoint returns combined weights + sections + optional platforms
2. **Frontend → Passport-platforms**: Resolves icons and provider definitions
3. **Frontend Logic**: Handles three data formats, filters by weight, formats response for UI

## Key Design Decisions

1. **Prefer platforms array over custom_stamps**: Cleaner, more explicit data format
2. **Backward compatibility**: Keep custom_stamps format working for older scorer implementations
3. **Icon resolution**: Custom platforms point to icon_platform_id for icon lookup
4. **Weight format**: Credentials store weight as string in response, but calculator uses numbers
5. **Empty credential arrays**: Custom platforms (AllowList, DeveloperList) have providers=[] in passport-platforms mock
**Files**: api/embed/api.py, embed/src/metadata.ts, embed/__tests__/metadataHandler.test.ts
---

