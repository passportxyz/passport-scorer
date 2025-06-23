# Human Points Program - Indexer Implementation Spec

## Overview
Modify the existing Rust indexer to track on-chain minting events for the Human Points Program.

## ⚠️ IMPORTANT: Architecture Update (December 2024)
The initial implementation created separate indexers for Human Points events. However, analysis revealed this approach has significant drawbacks:
- Multiple RPC connections to the same chain
- Duplicate retry/restart logic
- Inconsistent block tracking between event types
- Resource inefficiency

**Recommended approach**: Refactor to a unified indexer architecture where each chain has a single indexer that handles multiple event types (staking, passport mints, Human ID mints). See the "Unified Architecture Design" section below for details.

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

4. **Initial Human Points Indexer Implementation**
   - Created `human_points_indexer.rs` with basic event watching
   - Implemented EAS Attested event handler for passport mints
   - Implemented Human ID SBT Transfer event handler
   - Integration with postgres client for data persistence

### Current Implementation Status 🚧
The Human Points indexer is new and needs to be built with the unified architecture from the start. The existing staking indexers will be migrated to this architecture.

### Required Implementation Steps
1. **Unified Indexer Implementation**
   - Single indexer per chain handling all event types
   - Shared WebSocket connection and retry logic
   - Event routing based on contract address
   - Proper start block handling for each contract type

3. **Robustness Features**
   - Block tracking per event type
   - Historical data processing from contract deployment
   - Timeout/hang detection
   - Automatic restart and recovery mechanisms

## Unified Architecture Design

### Current Issues with Separate Indexers
The current implementation creates separate indexer instances for:
- Staking events (one per chain)
- Human Points events (one per chain)

This causes:
1. **Multiple RPC connections** to the same chain
2. **Duplicate block tracking** - each indexer tracks its own "last processed block"
3. **No shared retry logic** - each indexer implements its own timeout detection
4. **Start block confusion** - staking start blocks don't align with passport/Human ID deployment blocks

### Recommended Unified Design

#### 1. Single Indexer Per Chain
```rust
pub struct UnifiedChainIndexer {
    chain_config: ChainConfig,
    provider: Arc<Provider<Ws>>,
    postgres_client: Arc<PostgresClient>,
}

struct ChainConfig {
    chain_id: u32,
    rpc_url: String,
    
    // Feature flags
    staking_enabled: bool,
    human_points_enabled: bool,
    
    // Contract configs with individual start blocks
    staking: Option<ContractConfig>,
    passport_mint: Option<ContractConfig>,  
    human_id_mint: Option<ContractConfig>,  // Only for Optimism
}

struct ContractConfig {
    address: Address,
    start_block: u64,  // Each contract has its own deployment block
    schema_uid: Option<H256>,  // For EAS events
}
```

#### 2. Keep Existing Block Tracking
Continue using the current `stake_lastblock` table:
```sql
-- No changes needed to existing table
CREATE TABLE stake_lastblock (
    chain INTEGER,
    block_number NUMERIC
);
```

Each contract handler will simply check if the event block >= its deployment block before processing. This is simpler and avoids unnecessary complexity.

#### 3. Single Event Processing Loop
```rust
impl UnifiedChainIndexer {
    async fn process_all_events(&self) -> Result<()> {
        // Get the last processed block for this chain
        let query_start_block = self.get_query_start_block().await?;
        
        // Process historical blocks in batches
        self.process_historical_blocks(query_start_block).await?;
        
        // Watch for new events with single connection
        let filter = Filter::new().from_block(current_block);
        let mut stream = self.provider.watch(&filter).await?;
        
        while let Some(log) = stream.next().await {
            // Route to appropriate handler based on contract address
            // Each handler checks if block >= deployment_block before processing
            self.route_log(log).await?;
        }
    }
}
```

### Migration Steps
1. Build unified indexer structure for Human Points
2. Refactor existing staking indexers to unified structure
3. Update configuration to include all contract addresses per chain
4. Test with historical reindexing

### Benefits
- **Single RPC connection per chain** - reduces resource usage
- **Unified retry/restart logic** - all events benefit from robustness features
- **Consistent block tracking** - no race conditions or missed blocks
- **Easier operations** - one indexer to monitor/restart per chain
- **Proper start block handling** - each contract uses its deployment block
