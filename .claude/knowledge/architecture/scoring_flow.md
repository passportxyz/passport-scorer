# Scoring Flow Architecture

## V2 Stamps API Scoring Endpoint

The `/v2/stamps/{scorer_id}/score/{address}` endpoint follows this flow:

1. **AWS Lambda Handler** (`stamp_score_GET.py`)
   - Receives request
   - Calls `handle_scoring_for_account()` in `api_stamps.py`

2. **Score Processing** (`api_stamps.py`)
   - Creates/updates Passport and Score objects
   - Calls `ascore_passport()` from `registry/atasks.py`

3. **Passport Scoring** (`registry/atasks.py`)
   - Loads passport data from ceramic cache
   - Runs LIFO deduplication via `alifo()`
   - Calculates weighted score
   - Records events and human points

4. **Response**
   - Returns `V2ScoreResponse` with scores, stamps, and dedup info

### Key Database Tables

- **ceramic_cache**: Source of credentials
- **registry_passport**: User passport records
- **registry_stamp**: Validated stamps
- **registry_score**: Calculated scores with evidence/stamps/stamp_scores fields
- **registry_hashscorerlink**: LIFO deduplication tracking
- **registry_event**: Event tracking
- **human_points_* tables**: Points tracking if enabled

## Score Update Event Recording

The SCORE_UPDATE event is automatically recorded via Django's pre_save signal on the Score model. When a Score instance is saved with status=DONE, the signal handler in `registry/models.py:120-134` creates an Event object with action=SCORE_UPDATE.

**Important for Rust migration**: This happens outside the main scoring logic - we need to ensure this event is created after score persistence.

### Event Data Structure

The event data contains the serialized Score model using Django's `serializers.serialize("json", [score])`:

```json
[{
  "model": "registry.score",
  "pk": <primary_key>,
  "fields": {
    "passport": <passport_id>,
    "score": "decimal_value",
    "last_score_timestamp": "ISO timestamp",
    "status": "DONE",
    "error": null,
    "evidence": {...},
    "stamp_scores": {...},
    "stamps": {...},
    "expiration_date": "ISO timestamp"
  }
}]
```

## Rust Migration Requirements

### Simplified Response Structure

The Rust implementation can skip the legacy evidence structure since the v2 endpoint only returns:
- score (decimal)
- passing_score (boolean)
- threshold (decimal)
- stamps (dict with score/dedup/expiration per provider)
- last_score_timestamp
- expiration_timestamp
- error

The evidence field with rawScore/threshold/success is only for internal legacy compatibility and not exposed in v2 API responses.

### Django Table Compatibility

The Rust implementation MUST write to existing Django tables to maintain compatibility. This includes storing the evidence field (with rawScore, threshold, success) in the registry_score table even though v2 API doesn't expose it.

**Strategy**: Have clean Rust data models internally, then translate to Django's expected format when persisting to database.

### Migration Plan Status

The RUST_MIGRATION_PLAN.md has been finalized with complete implementation details including:
1. Nullifiers-only approach (no hash field support)
2. No feature flag filtering (process all nullifiers)
3. Django table compatibility requirements with exact field formats
4. LIFO retry mechanism for concurrent requests
5. Complete verification checklist for implementation team

**Key insight**: Maintain exact DB operation parity for accurate performance comparison in POC.

## Phase 1 Implementation Complete

Successfully completed Phase 1 of Rust migration for Passport Scorer v2 endpoint.

### Architectural Structure Created

1. **Clean Internal Models** (`StampData`, `ScoringResult`) for business logic
2. **Django-compatible database structs** matching existing tables exactly
3. **V2 API response types** with 5 decimal place formatting
4. **Translation layers** to convert between clean models and Django formats
5. **Comprehensive unit tests** (7 tests, all passing)

### Key Architectural Decisions

- **Separation of concerns**: Clean models for logic, Django compatibility only at boundaries
- **Future-ready**: `to_scoring_event()` method for event-driven architecture
- **Type safety**: Ensuring correct transformations
- **Single source of truth**: One model generates all output formats

### Critical Django Compatibility Maintained

- Evidence field format: `{"type": "ThresholdScoreCheck", "success": bool, "rawScore": string, "threshold": string}`
- Stamps dict includes all stamps (deduped with score="0.00000")
- stamp_scores only includes valid stamps for scoring
- Binary score is exactly 1 or 0 as Decimal type

### Project Structure

Created at `/workspace/project/rust-scorer/` with full Cargo.toml dependencies and modular code organization.

## Phase 2 Implementation Complete

Successfully completed Phase 2 - Database Layer with:
- Connection pooling with r2d2 and diesel
- Read/write operations for all Django tables
- Comprehensive error handling
- Bulk operations support

## Phase 3 Implementation Complete

Successfully completed Phase 3 - API Key & Credential Validation:

### API Key Validation (`auth/api_key.rs`)
- SHA512 hashing matching djangorestframework-api-key v2 exactly
- Format: "sha512$$<hex_hash>" 
- X-API-Key header checked first, then Authorization header
- Demo key aliases support via environment variable
- Constant-time comparison for security
- API usage tracking to AccountAPIKeyAnalytics table

### Credential Validation (`auth/credentials.rs`)
- Validates credentials from CeramicCache
- Only supports nullifiers array (no legacy hash field)
- Checks: provider, nullifiers non-empty, DID match, expiration, trusted issuer
- Full DIDKit integration for signature verification
- Returns ValidatedCredential with provider, nullifiers, expiration

## Phase 4 Implementation Complete

Successfully completed Phase 4 - LIFO Deduplication:

### LIFO Algorithm Implementation (`dedup/lifo.rs`)
- 5-retry mechanism for concurrent IntegrityError handling
- Hash link checking categorizes nullifiers as owned/clashing/expired
- Stamps deduped if ANY nullifiers clash with existing non-expired hash links
- Expired hash links can be taken over by new addresses
- Self-owned hash links get expiration updates
- Backfill mechanism for partial nullifier clashes
- Bulk operations using UNNEST for performance

### Testing Status
- Unit tests passing for all phases
- Integration tests created (require DATABASE_URL)

## Phase 5 Implementation Complete

Successfully completed Phase 5 - Score Calculation:

### Score Calculation Implementation (`scoring/calculation.rs`)
- **Weight Lookup with Customization**: Checks customization overrides first, falls back to base scorer weights
- **Provider Deduplication**: Only first stamp per provider contributes weight (critical for correct scoring)
- **Binary Score Calculation**: Returns Decimal(1) if raw_score >= threshold, else Decimal(0)
- **Decimal Precision**: Uses rust_decimal::Decimal for exact precision matching Python
- **Expiration Tracking**: Tracks earliest expires_at from all valid stamps
- **Clean Architecture**: Works with clean StampData models, translates to Django format at boundaries

### Testing Coverage
- Unit tests verify provider dedup, threshold boundaries, unknown providers, expiration tracking
- All edge cases covered with comprehensive test suite

## Phase 6 Implementation Complete

Successfully completed Phase 6 - Human Points Integration:

### Human Points Implementation (`human_points/`)
- **Module Structure**: Clean modular design with `models.rs` (action types/mappings) and `processing.rs` (core logic)
- **All 15 Action Types**: SCB, HKY, ISB/ISS/ISG, CSB/CSE/CST, PMT, HIM, HGO/HPH/HCH/HBI, MTA
- **Environment Config**: Simple std::env::var() approach for HUMAN_POINTS_ENABLED, _START_TIMESTAMP, _MTA_ENABLED
- **Key Features**:
  - Provider-based deduplication for Human Keys (latest nullifier as tx_hash)
  - 4+ community scoring bonus logic
  - MetaMask OG list checking with 5000 award limit
  - Bulk operations using PostgreSQL UNNEST
  - Points calculation with multiplier support (excluding HIM actions)
  - All operations within same transaction as score persistence
- **Direct SQL**: No ORM overhead, direct queries for performance

### Testing Coverage
- 6 unit tests covering config loading, action mappings, eligibility checks
- Integration point via `process_human_points()` function

## Phase 7 Implementation Complete

Successfully completed Phase 7 (API Response & Events) on November 13, 2024. Successfully integrated all 6 previous phases into working API endpoint:

### Implementation Details
- **Complete scoring flow**: 14 steps in score_address_handler function
- **Transaction management**: Proper boundaries with commit/rollback
- **Zero score handling**: Returns empty score for addresses with no credentials
- **Human Points integration**: Conditional processing with include_human_points query parameter
- **Event recording**: Both LIFO deduplication and score update events
- **V2 response format**: Exact format with 5 decimal precision

### Test Results
- 28 unit tests passing
- 7 integration tests passing
- 3 database tests passing
- Total: 38 tests all passing

### Status
Ready for Phase 8 (Lambda Deployment). The Rust implementation is functionally complete with full Django compatibility maintained.

## Migration Progress Summary

- **Phase 1**: Data Models & Schema ✅
- **Phase 2**: Database Layer ✅
- **Phase 3**: API Key & Credential Validation ✅
- **Phase 4**: LIFO Deduplication ✅
- **Phase 5**: Score Calculation ✅
- **Phase 6**: Human Points Integration ✅
- **Phase 7**: API Response & Events ✅