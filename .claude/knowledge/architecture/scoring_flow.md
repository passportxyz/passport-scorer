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