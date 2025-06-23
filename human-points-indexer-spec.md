# Human Points Program - Indexer Implementation Spec

## Overview
Modify the existing Rust indexer to track on-chain minting events for the Human Points Program.

## Scope
The indexer will track two types of on-chain events:
1. **Passport Mints** - Track mints across multiple chains
2. **Human ID SBT Mints** - Track only on Optimism

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
    chain_id INTEGER       -- For mint actions, the blockchain ID
);

-- Indexes
CREATE INDEX registry_hu_address_5fea1a_idx ON registry_humanpoints(address, action);
CREATE INDEX registry_hu_timesta_7c6e55_idx ON registry_humanpoints(timestamp);

-- Unique constraints for deduplication
CREATE UNIQUE INDEX idx_mint_actions 
ON registry_humanpoints(address, action, tx_hash) 
WHERE action IN ('passport_mint', 'human_id_mint');

-- Note: No multiplier table needed - points calculation happens at query time
```

### Insert Query
```sql
-- For mint actions (PMT, HIM) with chain info
INSERT INTO registry_humanpoints (address, action, timestamp, tx_hash, chain_id)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT DO NOTHING;

-- For actions without chain info
INSERT INTO registry_humanpoints (address, action, timestamp, tx_hash)
VALUES ($1, $2, $3, $4)
ON CONFLICT DO NOTHING;
```

## Event Types to Track

### 1. Passport Mints
- **Action Code**: `PMT` (3-character code)

Chain ID | Chain Descr. | EAS Address | schema UID
0xa | OP Mainnet | 0x4200000000000000000000000000000000000021 | 0xda0257756063c891659fed52fd36ef7557f7b45d66f59645fd3c3b263b747254
0xe708 | Linea | 0xaEF4103A04090071165F78D45D83A0C0782c2B2a | 0xa15ea01b11913fd412243156b40a8d5102ee9784172f82f9481e4c953fdd516d
0xa4b1 | Arbitrum | 0xbD75f629A22Dc1ceD33dDA0b68c546A1c035c458 | 0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912
0x144 | zkSync Era | 0x21d8d4eE83b80bc0Cc0f2B7df3117Cf212d02901 | 0xb68405dffc0b727188de5a3af2ecbbc544ab01aef5353409c5006ffff342d143
0x82750 | Scroll | 0xC47300428b6AD2c7D03BB76D05A176058b47E6B0 | 0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912
0x168 | Shape | 0x4200000000000000000000000000000000000021 | 0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912
0x2105 | Base | 0x4200000000000000000000000000000000000021 | 0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912

Watch the EAS contract for Attested events emitted when the attester calls EAS.
Attestations are only accepted by the resolver if valid, so no need to validate or check sender.

**EAS Attested Event Structure:**
```solidity
event Attested(
    address indexed recipient,  // The address receiving the attestation (passport holder)
    address indexed attester,   // The attester's address
    bytes32 uid,               // Unique attestation identifier
    bytes32 indexed schemaUID  // Must match the schema UID for each chain
);
```

Extract the `recipient` address as the minter for passport mint tracking.

### 2. Human ID SBT Mints
- **Action Code**: `HIM` (3-character code)
- **Chain**: Optimism only

Contract address: 0x2AA822e264F8cc31A2b9C22f39e5551241e94DfB

This inherits from IERC721 and emits a Transfer event when a new SBT is minted. These should each count as an SBT mint action.

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
    
    // Use block timestamp, not system time
    insert_action(
        address,
        "PMT",                  // 3-character action code
        event.block_timestamp,  // NOT Utc::now()
        event.tx_hash,
        Some(chain_id)          // chain ID
    );
}

on_human_id_mint_event(event) {
    // CRITICAL: Always lowercase addresses
    let address = event.minter.to_lowercase();
    
    // Use block timestamp, not system time
    insert_action(
        address,
        "HIM",                  // 3-character action code for Human ID mint
        event.block_timestamp,  // NOT Utc::now()
        event.tx_hash,
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
- The indexer only needs to populate the `chain_id` field - score tracking is handled by the scoring system

## Temporary Nature
This implementation is temporary for the points program duration. Consider:
- Feature flag to enable/disable points tracking
- Easy way to stop indexing without breaking existing functionality
- Clean separation from core indexing logic

## Testing
- Test duplicate handling (same tx_hash)
- Test multi-chain passport mint tracking
- Test chain_id population for mint events
- Test correct 3-character action codes (PMT, HIM)

## Implementation Progress

### Completed ✅
1. **Test Framework Refactoring**
   - Created `sql_generation.rs` module with pure functions for SQL generation
   - Removed complex mocking in favor of testable pure functions
   - All SQL generation is now separate from database connections

2. **SQL Generation Functions**
   - Implemented `generate_human_points_sql()` for Human Points inserts
   - Supports both passport mints (PMT) and Human ID mints (HIM)
   - Handles optional chain_id parameter
   - Ensures address lowercasing
   - Uses `ON CONFLICT DO NOTHING` for deduplication

3. **Comprehensive Test Coverage**
   - Tests for all staking event types (existing functionality)
   - Tests for Human Points SQL generation:
     - Passport mint with chain_id
     - Human ID SBT mint
     - Address lowercase conversion
     - Optional chain_id handling
   - Edge case tests:
     - Zero amounts
     - Maximum block numbers
     - Address case normalization

### Not Yet Implemented 🚧
1. **Event Handlers**
   - EAS Attested event handler for passport mints
   - Human ID SBT Transfer event handler
   - Integration with existing indexer architecture

2. **Configuration**
   - Contract addresses for each chain
   - Event signatures and decoding
   - Feature flag for enabling/disabling Human Points

3. **Main Indexer Integration**
   - Adding Human Points indexers to main.rs
   - Connecting event handlers to SQL generation functions
   - Error handling and retry logic
