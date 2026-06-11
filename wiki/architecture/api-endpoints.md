# API Endpoints

## V2 Stamps API (Primary)

Location: `api/v2/api/api_stamps.py` + `api/v2/aws_lambdas/`

- **GET /v2/stamps/{scorer_id}/score/{address}** (Lambda: passport-v2-stamp-score)
  - Main scoring endpoint; calls `handle_scoring_for_account()`
  - Auth: API key (read_scores permission)
  - Query param: include_human_points
  - Response: V2ScoreResponse with scores, stamps, dedup info
  - Priority: 2112 (updated from 2023)

- **GET /v2/stamps/{scorer_id}/score/{address}/history**
  - Score from event history; requires created_at timestamp query param
  - Auth: API key (historical_endpoint permission)
  - Response: V2ScoreResponse
  - Priority: 2022

- **GET /v2/stamps/metadata**
  - All available stamps metadata; cached 1 hour
  - Auth: API key
  - Response: List[StampDisplayResponse]

- **GET /v2/stamps/{address}**
  - Cursor-paginated credentials
  - Auth: API key
  - Query params: token (cursor), limit (1-1000, default 1000), include_metadata
  - Response: CursorPaginatedStampCredentialResponse

- **GET /v2/models/score/{address}**
  - Model analysis (Lambda: passport-v2-model-score)
  - Query param: model
  - Priority: 2021

## Ceramic Cache API (Legacy v1)

Location: `api/aws_lambdas/scorer_api_passport/v1/` + `api/ceramic_cache/api/v1.py`

Note: Uses JWT DID auth (HS256), not API key. Deprecated but still deployed.

- POST /authenticate - JWT DID auth
- GET /score - UI score
- POST /score - Detailed score
- GET /stamp - Get stamps
- POST /stamps/bulk - Add stamps
- PATCH /stamps/bulk - Update stamps
- DELETE /stamps/bulk - Delete stamps
- GET /weights - Scorer weights

Also Python internal scoring (api/ceramic_cache/api/v1.py calls `async_to_sync(handle_scoring_for_account())`).

Listener rule priorities: 1030-1039 range (updated from 1001-1010)

## Internal API Endpoints

Location: `api/internal/api.py` (no auth: internal ALB only)

### Scoring
- **GET /internal/score/v2/{scorer_id}/{address}** - Score without human points
- **POST /internal/embed/stamps/{address}** - Add stamps + rescore
- **GET /internal/embed/score/{scorer_id}/{address}** - Score with stamps
- **GET /internal/embed/weights** - Scorer weights (NO AUTH!)
- **GET /internal/embed/validate-api-key** - Validate partner API key

### Utility
- POST /internal/check-bans - Check credential bans
- POST /internal/check-revocations - Check credential revocations
- GET /internal/stake/gtc/{address} - GTC stakes
- GET /internal/stake/legacy-gtc/{address}/{round_id} - Legacy stakes
- GET /internal/cgrants/contributor_statistics - Contributor stats
- GET /internal/allow-list/{list}/{address} - Allow list membership
- GET /internal/customization/credential/{provider_id} - Credential definition

## Embed Lambda Functions

Location: `api/embed/lambda_fn.py` + `infra/aws/embed/index.ts`

Private VPC, no direct public access. Use internal ALB. Listener priorities: 2104-2106 (updated from 2100-2103)

- **POST /internal/embed/stamps/{address}** (embed-st)
  - Handler: `lambda_handler_save_stamps()`
  - Adds stamps + rescores

- **GET /internal/embed/validate-api-key** (embed-rl)
  - Handler: `lambda_handler_get_rate_limit()`
  - Returns AccountAPIKeySchema with embed_rate_limit

- **GET /internal/embed/score/{scorer_id}/{address}** (embed-gs)
  - Handler: `lambda_handler_get_score()`
  - Gets current score + stamps

## Auth Methods

- **API Key**: PBKDF2-SHA256 with SHA-256 fast-path migration (`api/account/api_key_validator.py`)
  - Prefix lookup, hashed_key verification
  - Permissions: read_scores, submit_passports, create_scorers, historical_endpoint
  - Rate limits per endpoint type

- **Internal API Key**: Bearer token in Authorization header (`api/internal/api.py`)
  - No user-facing auth; already inside VPC
  - Used by ceramic cache endpoints to call internal endpoints

- **JWT DID**: HS256 ceramic cache auth (legacy v1 endpoints)

## Shared Response Types

- V2ScoreResponse (primary public response)
- GetStampsWithV2ScoreResponse (stamps + score)
- CursorPaginatedStampCredentialResponse (paginated)
- V2ScoreHistoryResponse (event history)

## Rust Implementation Status

ALL 15 endpoints fully implemented:
1. Main V2 endpoint
2-4. Embed endpoints (3)
5-6. Ceramic cache endpoints (2)
7-15. Internal API endpoints (9)

13/13 comparison tests passing (Python/Rust parity verified)
