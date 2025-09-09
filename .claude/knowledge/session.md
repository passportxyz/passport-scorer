# Knowledge Capture Session - 2025-09-09

### [15:23] [architecture] Score Update Event Recording Mechanism
**Details**: The SCORE_UPDATE event is automatically recorded via Django's pre_save signal on the Score model. When a Score instance is saved with status=DONE, the signal handler in registry/models.py:120-134 creates an Event object with action=SCORE_UPDATE. This happens outside the main scoring logic, which is important for the Rust migration - we need to ensure this event is created after score persistence.
**Files**: api/registry/models.py
---

### [15:23] [pattern] LIFO Deduplication Retry Logic
**Details**: The LIFO deduplication has a retry mechanism with 5 attempts to handle IntegrityError exceptions that occur during concurrent requests. When two requests compete to claim the same hash, one will fail with IntegrityError, triggering a retry. The retry logic is in account/deduplication/lifo.py:21-36. After saving hash links, there's a verification step to ensure the expected number of links were created/updated.
**Files**: api/account/deduplication/lifo.py
---

### [15:23] [gotcha] Nullifier Handling Multi vs Single Mode
**Details**: The get_nullifiers function in lifo.py has a feature flag FF_MULTI_NULLIFIER that controls whether all nullifiers are used or only v0-prefixed ones. When OFF (default), only nullifiers starting with 'v0' are used for deduplication. This is critical for exact parity - the Rust implementation must respect this feature flag. The nullifiers come from credential.credentialSubject.nullifiers array or .hash field.
**Files**: api/account/deduplication/lifo.py:38-44
---

### [15:23] [pattern] Stamp Score Calculation - Provider Deduplication
**Details**: When calculating scores, only the first stamp from each provider contributes to the score. If multiple stamps exist with the same provider, subsequent ones get a score of 0. This happens in scorer_weighted/computation.py where it checks 'if stamp.provider not in scored_providers'. The earned_points dict tracks each provider's weight, setting duplicates to 0.
**Files**: api/scorer_weighted/computation.py:46-69, api/scorer_weighted/computation.py:164-188
---

### [18:28] [gotcha] Rust Migration - Nullifiers Array Only
**Details**: The Rust implementation will ONLY support the nullifiers array field (not the legacy hash field). All credentials must have credentialSubject.nullifiers as an array with 1 or more values. This simplifies the implementation compared to Python which handles both hash and nullifiers fields.
**Files**: RUST_MIGRATION_PLAN.md
---

### [18:29] [gotcha] Rust Migration - No Feature Flag for Nullifiers
**Details**: The Rust implementation will NOT implement the FF_MULTI_NULLIFIER feature flag. It will always process ALL nullifiers in the array without any v0 prefix filtering. This is a simplification from the Python implementation which conditionally filters nullifiers based on the feature flag.
**Files**: RUST_MIGRATION_PLAN.md
---

### [18:33] [architecture] Rust Migration - Simplified Response Structure
**Details**: The Rust implementation can skip the legacy evidence structure since the v2 endpoint only returns: score (decimal), passing_score (boolean), threshold (decimal), stamps (dict with score/dedup/expiration per provider), last_score_timestamp, expiration_timestamp, error. The evidence field with rawScore/threshold/success is only for internal legacy compatibility and not exposed in v2 API responses.
**Files**: api/v2/api/api_stamps.py
---

### [18:35] [architecture] Rust Migration - Django Table Compatibility Required
**Details**: The Rust implementation MUST write to existing Django tables to maintain compatibility. This includes storing the evidence field (with rawScore, threshold, success) in the registry_score table even though v2 API doesn't expose it. The strategy is to have clean Rust data models internally, then translate to Django's expected format when persisting to database.
**Files**: api/registry/models.py
---

### [18:43] [architecture] Rust Migration Plan Finalized
**Details**: The RUST_MIGRATION_PLAN.md has been updated with complete implementation details including: 1) Nullifiers-only approach (no hash field support), 2) No feature flag filtering (process all nullifiers), 3) Django table compatibility requirements with exact field formats, 4) LIFO retry mechanism for concurrent requests, 5) Complete verification checklist for implementation team. Key insight: maintain exact DB operation parity for accurate performance comparison in POC.
**Files**: RUST_MIGRATION_PLAN.md
---

