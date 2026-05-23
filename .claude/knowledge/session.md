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

### [03:00] [workflow] Container dev setup without root access
**Details**: This container (Debian 12 bookworm, Node.js base image) runs as 'node' user without root/sudo access. To set up the full dev environment:

1. Install micromamba from GitHub releases (static binary, no root needed)
2. Create passport-dev environment with: python=3.12, postgresql=14, redis-server, gcc, gxx, make, pkg-config, openssl, libpq
3. Create symlink: ar -> x86_64-conda-linux-gnu-ar (needed by ring crate)
4. Install Poetry via pip in micromamba env
5. Install Rust via rustup (installs to ~/.cargo)
6. PostgreSQL runs in userspace at ~/pgdata (owned by node user, no postgres system user needed)
7. Redis runs daemonized: redis-server --daemonize yes --bind 127.0.0.1

Key environment variables needed for Rust compilation:
- CC=$CONDA_PREFIX/bin/gcc
- AR=$CONDA_PREFIX/bin/ar
- LIBRARY_PATH, LD_LIBRARY_PATH, C_INCLUDE_PATH, PKG_CONFIG_PATH pointing to $CONDA_PREFIX
- SQLX_OFFLINE=true (uses cached .sqlx/ queries)

Activation helper script: source ~/activate-passport-dev.sh
**Files**: dev-setup/install-ubuntu-container.sh, dev-setup/setup-ubuntu.sh
---

### [14:08] [workflow] Ubuntu/container dev setup scripts overview
**Details**: Three new scripts were created for Ubuntu/Debian/container environments alongside the original Fedora scripts:

1. **install-ubuntu-container.sh** - For containers without root access. Uses micromamba for all deps (python, postgres, redis, gcc). Installs Rust via rustup. Creates ~/activate-passport-dev.sh for environment activation.

2. **setup-ubuntu.sh** - Database setup, Django migrations, test data creation. Works with the micromamba-installed PostgreSQL running in userspace.

3. **install-ubuntu.sh** - For Ubuntu systems with sudo/apt access (standard installs).

Key pattern: The scripts detect container vs systemd environments and adjust PostgreSQL/Redis startup accordingly. Container environments use direct binary execution with --daemonize instead of systemctl.

Tests verified working: `cd api && poetry run pytest account/test/test_account.py` passes all 4 tests.
**Files**: dev-setup/install-ubuntu-container.sh, dev-setup/setup-ubuntu.sh, dev-setup/install-ubuntu.sh
---

