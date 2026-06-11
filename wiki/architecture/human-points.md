# Human Points System

Tracks user actions and awards points across multiple action types and communities.

## Database Tables

- **registry_humanpoints**: Records actions (unique: address + action + chain_id + provider + tx_hash)
- **registry_humanpointscommunityqualifiedusers**: Passing scores per community (unique: address + community)
- **registry_humanpointsconfig**: Point values per action type with active flag
- **registry_humanpointsmultiplier**: User multipliers (default: 1x)

## Action Types

- **SCORING_BONUS (SCB)**: Awarded when user passes 4+ communities
- **HUMAN_KEYS (HKY)**: For stamps with valid nullifiers, deduped by provider
- **IDENTITY_STAKING_* (ISB/ISS/ISG)**: Bronze/Silver/Gold self-staking stamps
- **COMMUNITY_STAKING_* (CSB/CSE/CST)**: Beginner/Experienced/Trusted community staking
- **PASSPORT_MINT (PMT)**: Passport minting with chain_id
- **HUMAN_ID_MINT (HIM)**: Human ID minting (excluded from point totals)
- **HUMAN_TECH_* (HGO/HPH/HCH/HBI)**: Gov ID, Phone, Clean Hands, Biometric
- **METAMASK_OG (MTA)**: Special bonus for MetaMaskOG list addresses (max 5000 awards)

## Processing Flow

1. Check community.human_points_program=true and HUMAN_POINTS_ENABLED setting
2. Record passing score in qualified users table
3. Process stamp actions:
   - Human Keys: Use provider as dedup key, store latest nullifier as tx_hash
   - Provider-based actions: Map via STAMP_PROVIDER_TO_ACTION
4. Award scoring bonus if 4+ communities passed
5. Award MetaMask OG points if qualified and under limit

## Points Calculation

Raw SQL joins registry_humanpoints with registry_humanpointsconfig:
- Excludes HIM actions from total
- Applies multiplier from registry_humanpointsmultiplier
- Returns breakdown by action and chain_id

## API Response

Included only when `include_human_points=true` query parameter:
- points_data: total, eligibility, multiplier, breakdown
- possible_points_data: same structure for maximum possible

## Implementation Details

### Environment Variables

- HUMAN_POINTS_ENABLED: Enable/disable feature
- HUMAN_POINTS_START_TIMESTAMP: Start tracking timestamp
- HUMAN_POINTS_MTA_ENABLED: Enable MetaMask OG tracking

### Human Keys Behavior

- Latest nullifier stored as tx_hash
- Provider used as dedup key
- One Human Keys action per provider per address

### Bulk Operations

Use PostgreSQL UNNEST for bulk inserts rather than loops.

### Transaction Consistency

Keep all Human Points operations within same transaction as score persistence.

### Special Cases

Provider field uses empty string ("") not NULL for actions like SCORING_BONUS and METAMASK_OG.
