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

## Chain-scoped WaaP credentials and scores

- The Passport app signs the deployed-wallet SIWE statement on the connected chain. `/ceramic-cache/authenticate/v2` checks deployed bytecode and ERC-1271 on that exact chain and issues a short-lived RS256 token with `chain_wallet: true` and an EIP-155 DID. IAM signs stamps with that same DID and uses the existing nullifier generators.
- `GET/PATCH /v2/wallet-stamps` reads or replaces the authenticated wallet's active credentials. A null stamp deletes that provider from this wallet's cache. `POST /v2/wallet-stamps/score` lets the wallet holder rescore its own credentials.
- The `ceramic_cache_chainwalletstamp` partial unique index keys active rows by chain ID, address, and provider. Both scorers match the signed DID and exclude revoked proofs. The legacy cache and its indexes serve legacy tokens.
- Both score runtimes read active Silk membership for `GET /v2/stamps/{scorer_id}/score/{address}` and `GET /v2/stamps/{scorer_id}/score/eip155/{chain_id}/{address}`. The contract route requires a community key with `read_scores` and `linked_wallet_breakdown`. The WaaP address anchors the cluster, and only privileged responses show the wallet breakdown and each stamp's source wallet and chain. Contract member keys use `eip155:{chain_id}:{address}`.
- Store an individual score in `registry_chainwalletscore` by community, chain ID, and address. LIFO shares nullifier claims across wallets and records each claim's owning chain and address. The aggregate is computed from live membership on each request, so unlink removes the member from the next result and its contribution stays out of the legacy score history.

### Staging validation

- Deploy Silk's typed linkage route and Passport IAM support. Apply `registry.0061_chain_wallet_scores` and `ceramic_cache.0036_chain_wallet_stamps` before enabling the scorer. Configure `CHAIN_WALLET_SCORING_ENABLED=true`, `SILK_AUTH_SERVER_URL`, and the matching `SILK_SERVICE_API_KEY` in the scorer deployment, and `NEXT_PUBLIC_CHAIN_WALLET_SCORING_ENABLED=true` in the Passport app build. The scorer auth Lambda needs its existing SIWE signing key and RPC support for the connected chain.
- Use a disposable WaaP test account, a deployed ERC-1271 wallet with a credential on its chain, and a staging community key with linked-wallet access. Record the WaaP score before linking. Link on the wallet's chain, then query the WaaP address and the typed member route. Verify the stamp's source chain and address, unlink the member, and repeat the queries to confirm the aggregate drops its contribution and the former member route returns 404.

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
