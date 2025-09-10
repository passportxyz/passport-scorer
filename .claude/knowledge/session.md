### [14:07] [architecture] Phase 1 implementation requirements
**Details**: Phase 1 requires a Rust implementation of the `/v2/stamps/{scorer_id}/score/{address}` endpoint with:

1. Data Flow:
- Entry: AWS Lambda handler in v2/aws_lambdas/stamp_score_GET.py
- Calls handle_scoring_for_account() in v2/api/api_stamps.py
- Creates/updates Passport and Score records
- Calls ascore_passport() from registry/atasks.py
- Loads credentials from ceramic_cache table (filter: deleted_at IS NULL, no revocation)
- Validates credentials with didkit
- Runs LIFO deduplication via alifo()
- Calculates weighted score
- Returns V2ScoreResponse

2. Key Simplifications for Rust:
- Only support nullifiers array (no hash field support)
- Process ALL nullifiers (no FF_MULTI_NULLIFIER feature flag)
- Credentials must have 1+ nullifiers in array

3. Django Compatibility Requirements:
- Must write exact same data structure to existing tables
- Score.evidence field format: {"type": "ThresholdScoreCheck", "success": bool, "rawScore": string, "threshold": string}
- Score.stamps field: dict with provider -> {score, dedup, expiration_date}
- Score.stamp_scores field: provider -> weight mapping (only valid stamps, not deduped ones)
- Binary score: 1 if sum >= threshold, else 0
- Create SCORE_UPDATE event after score save (Django uses pre_save signal)

4. LIFO Deduplication:
- 5-retry mechanism for IntegrityError on concurrent requests
- Stamp is deduped if ANY nullifier clashes with existing hash links
- Backfill non-clashing nullifiers with clashing owner's data
- Only first stamp per provider contributes to score

5. Human Points (required for v1):
- Check community.human_points_program flag
- Record passing scores, stamp actions, scoring bonus (4+ communities)
- MetaMask OG bonus for specific provider
**Files**: api/v2/aws_lambdas/stamp_score_GET.py, api/v2/api/api_stamps.py, api/registry/atasks.py, api/account/deduplication/lifo.py, api/scorer_weighted/computation.py
---

### [14:16] [architecture] Rust Phase 1 Implementation Complete
**Details**: Successfully completed Phase 1 of Rust migration for Passport Scorer v2 endpoint.

Created complete data model architecture with:
1. Clean internal models (StampData, ScoringResult) for business logic
2. Django-compatible database structs matching existing tables exactly
3. V2 API response types with 5 decimal place formatting
4. Translation layers to convert between clean models and Django formats
5. Comprehensive unit tests (7 tests, all passing)

Key architectural decisions:
- Separation of concerns: Clean models for logic, Django compatibility only at boundaries
- Future-ready with to_scoring_event() method for event-driven architecture
- Type safety ensuring correct transformations
- Single source of truth - one model generates all output formats

Project structure created at /workspace/project/rust-scorer/ with full Cargo.toml dependencies and modular code organization.

Critical Django compatibility maintained:
- Evidence field format: {"type": "ThresholdScoreCheck", "success": bool, "rawScore": string, "threshold": string}
- Stamps dict includes all stamps (deduped with score="0.00000")
- stamp_scores only includes valid stamps for scoring
- Binary score is exactly 1 or 0 as Decimal type

Ready for Phase 2: Database Layer implementation.
**Files**: rust-scorer/src/models/internal.rs, rust-scorer/src/models/django.rs, rust-scorer/src/models/v2_api.rs, rust-scorer/src/models/translation.rs, rust-scorer/src/models/tests.rs, rust-scorer/PHASE1_COMPLETE.md
---

