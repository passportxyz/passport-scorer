# Human Points Program - Indexer Implementation Spec

## Overview
Modify the existing Rust indexer to track on-chain minting events for the Human Points Program.

## Scope
The indexer will track two types of on-chain events:
1. **Passport Mints** - Track mints across multiple chains
2. **Holonym SBT Mints** - Track only on Optimism

## Database Integration
Write directly to the `registry_humanpoints` table in the scorer database.

### Table Structure
```sql
-- Main points tracking table
CREATE TABLE registry_humanpoints (
    id BIGSERIAL PRIMARY KEY,
    address VARCHAR(100) NOT NULL,
    action VARCHAR(3) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tx_hash VARCHAR(100),
    community_id INTEGER,  -- For mint actions, the community ID
    chain_id INTEGER       -- For mint actions, the blockchain ID
);

-- Indexes
CREATE INDEX registry_hu_address_5fea1a_idx ON registry_humanpoints(address, action);
CREATE INDEX registry_hu_timesta_7c6e55_idx ON registry_humanpoints(timestamp);

-- Unique constraints for deduplication
CREATE UNIQUE INDEX idx_mint_actions 
ON registry_humanpoints(address, action, tx_hash) 
WHERE action IN ('passport_mint', 'holonym_mint');

-- Note: No multiplier table needed - points calculation happens at query time
```

### Insert Query
```sql
-- For mint actions (PMT, HIM) with community and chain info
INSERT INTO registry_humanpoints (address, action, timestamp, tx_hash, community_id, chain_id)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT DO NOTHING;

-- For actions without community/chain info
INSERT INTO registry_humanpoints (address, action, timestamp, tx_hash)
VALUES ($1, $2, $3, $4)
ON CONFLICT DO NOTHING;
```

## Event Types to Track

### 1. Passport Mints
- **Action Code**: `PMT` (3-character code)
- **Chains**: [TO BE FILLED - list of chains where passport can be minted]
- **Contract**: [TO BE FILLED]
- **Event**: [TO BE FILLED]

### 2. Holonym SBT Mints (Human ID)
- **Action Code**: `HIM` (3-character code)
- **Chain**: Optimism only
- **Contract**: [TO BE FILLED]
- **Event**: [TO BE FILLED]

## Implementation Notes

### Points Calculation
- **IMPORTANT**: The indexer does NOT calculate or store points
- Only record that an action occurred with its timestamp and transaction hash
- Points calculation happens at query time in Django based on action type
- This allows point values to be changed without data migrations

### Data to Extract from Events
- `address`: The minter's address (**MUST convert to lowercase** for consistency)
- `tx_hash`: Transaction hash for deduplication
- `timestamp`: **Use block timestamp from the event**, NOT current time
- `chain_id`: For identifying which chain the mint occurred on
- `community_id`: **NEW** - For mint actions, extract the community ID from the event (if available)

### Database Writes
- Use the existing database connection pool
- Batch inserts where possible for efficiency
- Handle conflicts gracefully (ON CONFLICT DO NOTHING)
- Log successful point additions for monitoring

### Example Flow
```rust
// Pseudo-code
on_passport_mint_event(event) {
    // CRITICAL: Always lowercase addresses
    let address = event.minter.to_lowercase();
    
    // Extract community_id from event (implementation depends on event structure)
    let community_id = event.community_id; // or however it's encoded in the event
    
    // Use block timestamp, not system time
    insert_action(
        address,
        "PMT",                  // 3-character action code
        event.block_timestamp,  // NOT Utc::now()
        event.tx_hash,
        Some(community_id),     // community ID
        Some(chain_id)          // chain ID
    );
}

on_human_id_mint_event(event) {
    // CRITICAL: Always lowercase addresses
    let address = event.minter.to_lowercase();
    
    // Extract community_id if available
    let community_id = event.community_id;
    
    // Use block timestamp, not system time
    insert_action(
        address,
        "HIM",                  // 3-character action code for Human ID mint
        event.block_timestamp,  // NOT Utc::now()
        event.tx_hash,
        Some(community_id),
        Some(10)                // Optimism chain ID
    );
}
```

## Configuration
Add configuration for:
- Enable/disable Human Points tracking
- Contract addresses per chain
- Event signatures
- Action code mappings (PMT for passport mints, HIM for Human ID mints)

## Model Changes Update
The Django models have been refactored:
- `HumanPointProgramStats` replaced with `HumanPointProgramScores`
- The scoring system now tracks which specific communities an address has passing scores in
- This ensures proper enforcement of the "3 different approved communities" requirement
- The indexer only needs to populate `community_id` and `chain_id` fields - score tracking is handled by the scoring system

## Temporary Nature
This implementation is temporary for the points program duration. Consider:
- Feature flag to enable/disable points tracking
- Easy way to stop indexing without breaking existing functionality
- Clean separation from core indexing logic

## Testing
- Test duplicate handling (same tx_hash)
- Test multi-chain passport mint tracking
- Test community_id and chain_id population for mint events
- Test correct 3-character action codes (PMT, HIM)
