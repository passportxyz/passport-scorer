# Complete API and Lambda Endpoint Map

## Overview

Comprehensive mapping of all scoring-related endpoints and Lambda functions in the codebase.

## V2 API Endpoints (Primary Public API)

Location: `/api/v2/api/api_stamps.py`
Routes served via: Django Ninja + ALB routing

### 1. GET /v2/stamps/{scorer_id}/score/{address}
- **Lambda**: passport-v2-stamp-score (stamp_score_GET.py)
- **Handler**: a_submit_passport() async
- **Auth**: API Key required (aapi_key)
- **Response**: V2ScoreResponse
- **Features**:
  - Main scoring endpoint - calls handle_scoring_for_account()
  - Supports include_human_points query param for human points integration
  - Tracked via atrack_apikey_usage()
- **Priority**: 2023, Timeout: 60s

### 2. GET /v2/stamps/{scorer_id}/score/{address}/history
- **Lambda**: via targetGroupRegistry (Django endpoint, not standalone Lambda)
- **Handler**: get_score_history()
- **Auth**: API Key required (historical_endpoint permission)
- **Response**: V2ScoreResponse (from event history)
- **Features**:
  - Requires created_at timestamp query param
  - Accesses Event model for historical score lookups
- **Priority**: 2022

### 3. GET /v2/stamps/metadata
- **Handler**: stamp_display()
- **Auth**: API Key required
- **Response**: List[StampDisplayResponse]
- **Features**:
  - Returns all available stamps metadata
  - Cached for 1 hour

### 4. GET /v2/stamps/{address}
- **Handler**: get_passport_stamps()
- **Auth**: API Key required
- **Response**: CursorPaginatedStampCredentialResponse
- **Query params**:
  - token (cursor)
  - limit (default 1000, max 1000)
  - include_metadata (boolean)
- **Features**:
  - Cursor-based pagination on CeramicCache records
  - Optionally includes stamp metadata if requested

## Models/Analysis Endpoints

Location: `/api/v2/aws_lambdas/`

### GET /v2/models/score/{address}
- **Lambda**: passport-v2-model-score (models_score_GET.py)
- **Handler**: _handler() → handle_get_analysis()
- **Response**: Model analysis data
- **Query param**: model (model_list)
- **Priority**: 2021, Timeout: 90s
- Uses ceramic_cache.api.v1.handle_get_analysis()

## Scorer API V1 Endpoints (Legacy Internal API)

Location: `/api/aws_lambdas/scorer_api_passport/v1/`

**Note**: These are deprecated but still deployed. Use internal API instead for new integrations.

1. **POST /authenticate** - JWT DID authentication
2. **GET /score** - UI score with JWT auth
3. **POST /score** - Detailed score with JWT auth
4. **GET /stamp** - Get stamps for authenticated user
5. **POST /stamps/bulk** - Add stamps with JWT auth
6. **PATCH /stamps/bulk** - Update stamps with JWT auth
7. **DELETE /stamps/bulk** - Delete stamps with JWT auth
8. **GET /weights** - Get scorer weights configuration

## Internal API Endpoints

Location: `/api/internal/api.py`
Auth: internal_api_key authentication

### Core Scoring
- **GET /score/v2/{scorer_id}/{address}** - Internal scoring without human points
- **POST /embed/stamps/{address}** - Add stamps and rescore
- **GET /embed/score/{scorer_id}/{address}** - Get score with stamps
- **GET /embed/weights** - Get scorer weights (NO AUTH!)
- **GET /embed/validate-api-key** - Validate partner API key

### Utility Endpoints
- **POST /check-bans** - Check credential bans
- **POST /check-revocations** - Check credential revocations
- **GET /stake/gtc/{address}** - Get GTC stake
- **GET /stake/legacy-gtc/{address}/{round_id}** - Legacy GTC stake
- **GET /cgrants/contributor_statistics** - Contributor stats
- **GET /allow-list/{list}/{address}** - Check allow list membership
- **GET /customization/credential/{provider_id}** - Get credential customization

## Embed Lambda Functions

Location: `/api/embed/lambda_fn.py`
Deployed via: `/infra/aws/embed/index.ts`
Private VPC, no direct public access

All Embed lambdas have internal_api_key auth and serve via private internal ALB:

### 1. POST /internal/embed/stamps/{address} (embed-st)
- **Lambda handler**: lambda_handler_save_stamps()
- **Payload**: AddStampsPayload (scorer_id, stamps)
- **Response**: GetStampsWithV2ScoreResponse
- **Priority**: 2100
- Adds stamps + rescores passport

### 2. GET /internal/embed/validate-api-key (embed-rl)
- **Lambda handler**: lambda_handler_get_rate_limit()
- **Response**: AccountAPIKeySchema (embed_rate_limit)
- **Priority**: 2101
- Validates API key and returns rate limit config

### 3. GET /internal/embed/score/{scorer_id}/{address} (embed-gs)
- **Lambda handler**: lambda_handler_get_score()
- **Response**: GetStampsWithV2ScoreResponse
- **Priority**: 2102
- Gets current score + stamps for address

## Other Endpoints

- **GET /passport/analysis/{address}** - Model analysis
- **POST /submit_passport** - Create/update passport and submit for scoring
- **SQS Trigger** (rescore.py) - Batch rescoring from queue
- **GET /showmigrations** - Django migration status (dev/admin)

## Key Shared Dependencies

### Authentication & Authorization
- API Key validation: AccountAPIKey with PBKDF2-SHA256 fast-path + SHA-256 verification
- Demo API key aliases via settings.DEMO_API_KEY_ALIASES
- Internal API key: internal_api_key auth class
- JWT DID auth: JWTDidAuthentication for legacy endpoints

### Core Functions
- `handle_scoring_for_account()` - main scoring flow with optional human points
- `ahandle_scoring()` - async scoring without human points
- `ascore_passport()` - core scoring task via registry.atasks
- `handle_add_stamps_only()` - add stamps without rescoring
- `handle_embed_add_stamps()` - add stamps + rescore
- `get_user_points_data()` - human points calculation
- `get_possible_points_data()` - possible points calculation

### Database Models
- Community/Scorer (scorer_id identifies community)
- Passport (per address per community)
- Score (latest score for passport)
- Event (score history via SCORE_UPDATE action)
- CeramicCache (stamp credentials)
- AccountAPIKey (API key management)
- HumanPointsConfig (points configuration)

### Response Types
- V2ScoreResponse (primary response type)
- GetStampsWithV2ScoreResponse (stamps + score)
- CursorPaginatedStampCredentialResponse (paginated stamps)
- Various legacy response types (for v1 API)

## Rust Implementation Requirements

### Must Implement
1. All V2 API endpoints (/v2/stamps/*)
2. Internal API scoring endpoints (/internal/score/v2/*, /internal/embed/*)
3. Embed Lambda functions (save stamps, get score, validate API key)
4. API key authentication with SHA-256 fast path
5. Human points integration if enabled
6. Event recording for score updates
7. Cursor pagination for stamps endpoint

### Not Required (Legacy/Deprecated)
- Scorer API V1 endpoints (use internal API instead)
- Passport analysis endpoints (separate service concern)
- Submit passport endpoint (different service boundary)
- Rescore SQS handler (batch operation)

See: `api/v2/api/api_stamps.py`, `api/v2/aws_lambdas/`, `api/embed/lambda_fn.py`, `api/internal/api.py`, `infra/aws/`