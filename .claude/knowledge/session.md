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

### [12:14] [architecture] V2 Stamps API scoring endpoint flow
**Details**: The /v2/stamps/{scorer_id}/score/{address} endpoint follows this flow:
1. AWS Lambda handler in stamp_score_GET.py receives request
2. Calls handle_scoring_for_account() in api_stamps.py
3. Creates/updates Passport and Score objects 
4. Calls ascore_passport() from registry/atasks.py which:
   - Loads passport data from ceramic cache
   - Runs LIFO deduplication via alifo() 
   - Calculates weighted score
   - Records events and human points
5. Returns V2ScoreResponse with scores, stamps, and dedup info

Key tables involved:
- ceramic_cache: Source of credentials
- registry_passport: User passport records
- registry_stamp: Validated stamps
- registry_score: Calculated scores with evidence/stamps/stamp_scores fields
- registry_hashscorerlink: LIFO deduplication tracking
- registry_event: Event tracking
- human_points_* tables: Points tracking if enabled
**Files**: api/v2/aws_lambdas/stamp_score_GET.py, api/v2/api/api_stamps.py, api/registry/atasks.py, api/account/deduplication/lifo.py
---

### [12:14] [gotcha] LIFO deduplication nullifier handling complexity
**Details**: The Python LIFO implementation has complex logic:
1. Supports both legacy 'hash' field and newer 'nullifiers' array in credentialSubject
2. Uses FF_MULTI_NULLIFIER feature flag to filter nullifiers (only v0 prefixed when off)
3. A stamp is deduped if ANY of its nullifiers clash with existing hash links
4. When some but not all nullifiers clash, it backfills non-clashing nullifiers with the clashing owner's data
5. Implements 5-retry mechanism for IntegrityError handling on concurrent requests
6. Updates expired hash links by reassigning to new owner

This is simplified in the Rust plan to only support nullifiers array with no filtering.
**Files**: api/account/deduplication/lifo.py
---

### [12:21] [api] API Key Authentication Mechanism
**Details**: API keys use djangorestframework-api-key (v2) with AbstractAPIKey model. Keys are stored with:
- Prefix (first 8 chars) for lookup
- Hashed key for security
- Permissions: submit_passports, read_scores, create_scorers, historical_endpoint
- Rate limits: separate for standard, analysis, and embed endpoints
- Analytics tracking via AccountAPIKeyAnalytics table

Authentication flow:
1. Check X-API-Key header first, then Authorization header
2. Look up by prefix, verify against hashed_key
3. Attach to request.api_key for usage tracking
4. Special handling for DEMO_API_KEY_ALIASES

Database tables:
- account_accountapikey: API key storage with permissions
- account_accountapikeyanalytics: Usage tracking with paths, payloads, responses
**Files**: api/registry/api/utils.py, api/account/models.py
---

### [12:21] [dependency] didkit version for credential validation
**Details**: Python uses didkit = "*" (any version) in pyproject.toml. This is used for credential validation through Python FFI. For Rust implementation, need to verify exact version compatibility. The Python code calls didkit for signature verification with proofPurpose="assertionMethod".
**Files**: api/pyproject.toml
---

### [12:21] [config] Django database connection configuration
**Details**: Django uses multiple database connections:
- default: Main database from DATABASE_URL env var
- data_model: Separate DB for data model from DATA_MODEL_DATABASE_URL
- read_replica_0: Read replica from READ_REPLICA_0_URL
- read_replica_analytics: Analytics read replica from READ_REPLICA_ANALYTICS_URL

No explicit connection pooling or CONN_MAX_AGE settings found in base.py, meaning Django uses default behavior (new connection per request). In Lambda, connections are closed after each request via close_old_connections().

For Rust: RDS Proxy handles connection pooling at infrastructure level, so low connection count (5) in app is appropriate.
**Files**: api/scorer/settings/base.py, api/v2/aws_lambdas/stamp_score_GET.py
---

### [12:22] [api] Complete Human Points implementation requirements
**Details**: Human Points system tracks user actions and awards points. Key components:

DATABASE TABLES:
1. registry_humanpoints: Records actions (with unique constraint on address+action+chain_id+provider+tx_hash)
2. registry_humanpointscommunityqualifiedusers: Tracks passing scores per community (unique on address+community)
3. registry_humanpointsconfig: Point values per action type (active flag for enabling/disabling)
4. registry_humanpointsmultiplier: User multipliers (default 2x)

ACTION TYPES:
- SCORING_BONUS (SCB): Awarded when user has 4+ passing scores across communities
- HUMAN_KEYS (HKY): For stamps with valid nullifiers, deduplicated by provider
- IDENTITY_STAKING_* (ISB/ISS/ISG): Bronze/Silver/Gold self-staking stamps
- COMMUNITY_STAKING_* (CSB/CSE/CST): Beginner/Experienced/Trusted community staking
- PASSPORT_MINT (PMT): Passport minting with chain_id
- HUMAN_ID_MINT (HIM): Human ID minting (excluded from point calculations)
- HUMAN_TECH_* (HGO/HPH/HCH/HBI): Gov ID, Phone, Clean Hands, Biometric stamps
- METAMASK_OG (MTA): Special bonus for addresses in MetaMaskOG list (max 5000 awards)

PROCESSING FLOW:
1. Check if community has human_points_program=true and HUMAN_POINTS_ENABLED setting
2. Record passing score in qualified users table (arecord_passing_score)
3. Process stamp actions (arecord_stamp_actions):
   - Human Keys: Use provider as dedup key, store latest nullifier as tx_hash
   - Provider-based: Map stamp providers to action types via STAMP_PROVIDER_TO_ACTION
4. Award scoring bonus if 4+ communities passed (acheck_and_award_scoring_bonus)
5. Award MetaMask OG points if on list and under 5000 limit (acheck_and_award_misc_points)

POINTS CALCULATION:
- Raw SQL query joins registry_humanpoints with registry_humanpointsconfig
- Excludes HIM actions from total
- Applies multiplier from registry_humanpointsmultiplier
- Returns breakdown by action and chain_id

API RESPONSE:
- Only included if include_human_points=true parameter
- Returns points_data and possible_points_data with total, eligibility, multiplier, breakdown
**Files**: api/registry/models.py, api/registry/human_points_utils.py, api/registry/atasks.py, api/v2/api/api_stamps.py
---

