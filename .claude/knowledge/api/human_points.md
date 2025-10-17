# Human Points System

## Complete Implementation Requirements

Human Points system tracks user actions and awards points.

### Database Tables

1. **registry_humanpoints**: Records actions (unique constraint on address+action+chain_id+provider+tx_hash)
2. **registry_humanpointscommunityqualifiedusers**: Tracks passing scores per community (unique on address+community)
3. **registry_humanpointsconfig**: Point values per action type (active flag for enabling/disabling)
4. **registry_humanpointsmultiplier**: User multipliers (default 1x)

### Action Types

- **SCORING_BONUS (SCB)**: Awarded when user has 4+ passing scores across communities
- **HUMAN_KEYS (HKY)**: For stamps with valid nullifiers, deduplicated by provider
- **IDENTITY_STAKING_* (ISB/ISS/ISG)**: Bronze/Silver/Gold self-staking stamps
- **COMMUNITY_STAKING_* (CSB/CSE/CST)**: Beginner/Experienced/Trusted community staking
- **PASSPORT_MINT (PMT)**: Passport minting with chain_id
- **HUMAN_ID_MINT (HIM)**: Human ID minting (excluded from point calculations)
- **HUMAN_TECH_* (HGO/HPH/HCH/HBI)**: Gov ID, Phone, Clean Hands, Biometric stamps
- **METAMASK_OG (MTA)**: Special bonus for addresses in MetaMaskOG list (max 5000 awards)

### Processing Flow

1. Check if community has human_points_program=true and HUMAN_POINTS_ENABLED setting
2. Record passing score in qualified users table (`arecord_passing_score`)
3. Process stamp actions (`arecord_stamp_actions`):
   - Human Keys: Use provider as dedup key, store latest nullifier as tx_hash
   - Provider-based: Map stamp providers to action types via STAMP_PROVIDER_TO_ACTION
4. Award scoring bonus if 4+ communities passed (`acheck_and_award_scoring_bonus`)
5. Award MetaMask OG points if on list and under 5000 limit (`acheck_and_award_misc_points`)

### Points Calculation

- Raw SQL query joins registry_humanpoints with registry_humanpointsconfig
- Excludes HIM actions from total
- Applies multiplier from registry_humanpointsmultiplier
- Returns breakdown by action and chain_id

### API Response

- Only included if `include_human_points=true` parameter
- Returns `points_data` and `possible_points_data` with total, eligibility, multiplier, breakdown

### Rust Implementation Details

1. **Environment Variables**: Read from env using simple `std::env::var` approach
   - HUMAN_POINTS_ENABLED
   - HUMAN_POINTS_START_TIMESTAMP  
   - HUMAN_POINTS_MTA_ENABLED

2. **MetaMask OG List**: Directly query `account_addresslist` and `account_addresslistmember` tables with hardcoded queries

3. **Human Keys Behavior**: 
   - Use latest nullifier as tx_hash
   - Provider as dedup key
   - Only one Human Keys action per provider

4. **Transaction Consistency**: Keep Human Points operations within same transaction as score persistence

5. **Bulk Operations**: Use PostgreSQL UNNEST for bulk inserts rather than individual insert loops

6. **Points Calculation**: 
   - Must exclude HIM actions from total points
   - Default multiplier is 1
   - Chain-specific actions use format: action_chainid in breakdown

See `api/registry/models.py`, `api/registry/human_points_utils.py`, `api/registry/atasks.py`, `api/v2/api/api_stamps.py`, `rust-scorer/src/human_points/`