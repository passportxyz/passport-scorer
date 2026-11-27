# Scoring Flow Architecture

Primary entry point is `/v2/stamps/{scorer_id}/score/{address}` endpoint. Ceramic cache endpoints trigger the same flow via `async_to_sync()` wrapper in Python.

## Main Scoring Pipeline

1. **AWS Lambda Handler** (`api/v2/aws_lambdas/stamp_score_GET.py`)
   - Receives request with API key auth
   - Calls `handle_scoring_for_account()` in `api_stamps.py`

2. **Score Processing** (`api/v2/api/api_stamps.py`)
   - Creates/updates Passport and Score objects
   - Calls `ascore_passport()` from `api/registry/atasks.py`

3. **Passport Scoring** (`api/registry/atasks.py`)
   - Loads credentials from ceramic_cache table
   - Runs LIFO deduplication via `alifo()` in `api/account/deduplication/lifo.py`
   - Calculates weighted score
   - Records SCORE_UPDATE events and human points

4. **Response**
   - Returns `V2ScoreResponse` with scores, stamps, dedup info
   - If `include_human_points=true`: includes points breakdown

## Chain-scoped WaaP wallet scores

- Python (including the stamp score Lambda) and Rust serve `GET /v2/stamps/{scorer_id}/score/eip155/{chain_id}/{address}`. The caller needs a key for the community with `read_scores` and `linked_wallet_breakdown`.
- Apply Django migration `registry.0061_chain_wallet_scores` before deploying either runtime. To enable scoring, set `CHAIN_WALLET_SCORING_ENABLED=true`, `SILK_AUTH_SERVER_URL`, and `SILK_SERVICE_API_KEY` in both environments. Each request checks the exact active contract identity in Silk's service-key API. An unavailable lookup fails the request.
- Match the signed `did:pkh:eip155:{chain_id}:{address}` before selecting the latest active stamp per provider. The legacy Passport sign-in issues mainnet DIDs, and its stamp cache allows one active credential per address, provider, and cache type. Non-mainnet rollout needs chain-specific credential issuance and cache writes that preserve each chain's active credential.
- Store the latest response in `registry_chainwalletscore` by community, chain ID, and lowercase address. LIFO keeps one claim per nullifier and community, with the claiming identity recorded as chain ID and address. Existing owners map to chain 1, the DID chain used by legacy scoring.
- Scoped scores are single-wallet results. Cluster aggregation needs to consume Silk's typed wallet identities separately.

## Database Tables

- **ceramic_cache**: Credential records (type='V1' only, V2 abandoned)
- **registry_passport**: User passport per community
- **registry_stamp**: Validated stamps linked to passport
- **registry_score**: Latest score with evidence/stamps/stamp_scores JSON fields
- **registry_hashscorerlink**: LIFO dedup hash tracking with expiration
- **registry_event**: Event history (SCORE_UPDATE on score save)
- **registry_humanpoints***: Points tracking (if enabled)

## Score Update Event Recording

Django pre_save signal on Score model (registry/models.py:120-134) automatically creates Event with action=SCORE_UPDATE when status='DONE'. Event data is Django-serialized Score model:

```json
[{
  "model": "registry.score",
  "pk": <id>,
  "fields": {
    "passport": <passport_id>,
    "score": "1.23456",
    "last_score_timestamp": "2026-04-14T...",
    "status": "DONE",
    "error": null,
    "evidence": {"type": "ThresholdScoreCheck", "success": bool, "rawScore": "...", "threshold": "..."},
    "stamp_scores": {"provider": "0.50000", ...},
    "stamps": {"provider": {"score": "0.50000", "dedup": false, "expiration": "2026-05-14T..."}, ...},
    "expiration_date": "2026-05-14T..."
  }
}]
```

## Ceramic Cache Integration

Ceramic cache endpoints (POST /ceramic-cache/stamps/bulk, GET /ceramic-cache/score/{address}) call same scoring flow but wrap async code in `async_to_sync()`, creating performance bottleneck. Python code calls:
- `get_detailed_score_response_for_address()` → `async_to_sync(handle_scoring_for_account())`

Rust migration can skip this wrapper and call async directly or provide internal HTTP endpoint.

## Django Compatibility Requirements

Rust implementation must write to Django tables with exact format:
- Evidence field: `{"type": "ThresholdScoreCheck", "success": bool, "rawScore": "string", "threshold": "string"}`
- Stamps dict includes ALL stamps (deduped stamps have score="0.00000")
- stamp_scores only includes valid (non-deduped) stamps
- Binary score is exactly Decimal(1) or Decimal(0)
- All timestamps are ISO 8601 strings with timezone

## Performance Bottlenecks

1. **Async_to_sync wrapper**: Python's ceramic cache endpoints use `async_to_sync()` on async scoring function
2. **RDS Proxy connection acquisition**: 15-20 second delays under load when creating new connections
3. **Django CONN_MAX_AGE=0**: Forces new connection per request; `close_old_connections()` called at start of each Lambda

Performance targets: Cold start <100ms, P50 <100ms, P95 <200ms, P99 <500ms, Memory <256MB
