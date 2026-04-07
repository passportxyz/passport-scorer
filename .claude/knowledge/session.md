### [17:50] [gotcha] Linked wallets: skip-DONE optimization is unsafe
**Details**: When scoring wallet groups, we considered skipping re-scoring for wallets with status=DONE and non-expired scores. This is NOT SAFE because:

1. Ceramic cache updates (stamp add/remove) do NOT set Score.status to PROCESSING. The Score stays DONE with stale stamps.
2. LIFO dedup state depends on other wallets in the community (not just the group). Skipping re-score means stale dedup flags.
3. Stamp revocations can happen outside expiration — we'd miss revoked stamps.

To make it viable, you'd need to compare CeramicCache.updated_at vs Score.last_score_timestamp per wallet, but that still misses cross-wallet dedup changes.

Decision: Ship with serial re-scoring of all group members (capped at MAX_GROUP_SIZE=10). Optimize later only if production metrics show it's actually slow.
**Files**: api/v2/api/api_stamps.py, api/registry/atasks.py, api/ceramic_cache/api/v1.py
---

### [17:50] [architecture] Linked wallets: canonical scoring and stamp merging design
**Details**: Linked wallets merge stamps across a wallet group for scoring. Key design decisions:

1. Canonical wallet is first-to-request per community, tracked in WalletGroupCommunityClaim table (unique on group+community)
2. Canonical gets the combined score; non-canonical wallets return score=0 with linked_score pointer
3. Stamp merging: iterate wallets canonical-first, take first non-deduped stamp per provider
4. Weight lookup: use stamp_scores from individual Score objects (already computed by ascore_passport) instead of re-loading weights — avoids duplicating weight loading logic
5. Double SCORE_UPDATE fix: pass persist=False to ascore_passport for canonical wallet, since we overwrite with merged score immediately after
6. Score invalidation on unlink: set affected scores to PROCESSING status, rescore happens on next request (lazy)
7. Group size capped at MAX_GROUP_SIZE=10
8. SIWE signatures required for all link/add/unlink operations
**Files**: api/v2/api/api_stamps.py, api/account/api_wallet_groups.py, api/account/models.py, rust-scorer/src/domain/scoring.rs
---

