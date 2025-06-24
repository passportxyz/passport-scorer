# Human Points Program - Indexer Implementation Spec

## Overview
Modify the existing Rust indexer to track on-chain minting events for the Human Points Program.

## ⚠️ IMPORTANT: Architecture Update
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

## Background: How We Got Here

### Current Production Status
- **Staking Indexers**: ✅ **IN PRODUCTION** - These are live and processing real data. Must be preserved carefully during migration.
- **Human Points Indexers**: 🚧 **NEW DEVELOPMENT** - Only exists in this development branch. No production data to preserve.

### Initial Development Approach
During development, we initially built separate indexers for Human Points events (passport mints and Human ID mints) alongside the existing production staking indexers. This resulted in:
- Multiple WebSocket connections to the same RPC endpoint
- Duplicate retry/timeout logic across indexers
- Each indexer managing its own lifecycle independently
- Human Points indexer lacking robustness features (block tracking, recovery, etc.)

### The Problem
Running multiple indexers per chain is inefficient and error-prone:
- Resource waste from duplicate connections
- Complex coordination between indexers
- Inconsistent error handling and recovery
- Difficult to maintain and monitor

### The Solution: Unified Indexer Architecture
Since Human Points is brand new, we can build it correctly from the start with a unified architecture:
- **One indexer per chain** handling all event types
- **Shared WebSocket connection** and retry logic
- **Single block tracker per chain** (existing `stake_lastblock` table)
- **Each contract handler checks deployment block** before processing events

This approach allows us to:
1. Build Human Points the right way from the beginning
2. Carefully migrate production staking indexers without disruption
3. Avoid creating technical debt we'd have to fix later

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

4. **Initial Human Points Indexer Implementation** (Development only)
   - Created `human_points_indexer.rs` with basic event watching
   - Implemented EAS Attested event handler for passport mints
   - Implemented Human ID SBT Transfer event handler
   - Integration with postgres client for data persistence
   - **Note**: This implementation is being replaced with unified architecture before production

5. **Unified Indexer Implementation** ✅
   - Created `unified_indexer.rs` with `UnifiedChainIndexer` struct
   - Single indexer per chain handling all event types (staking + Human Points)
   - Shared WebSocket connection and retry logic
   - Event routing based on contract address with deployment block checking
   - Proper start block handling for each contract type
   - Successfully integrated all existing robustness features:
     - 15-minute timeout detection
     - Automatic restart on errors
     - Block tracking and recovery
     - Historical block processing in batches

### Current Implementation Status ✅
The unified indexer architecture is complete and fully integrated. The implementation includes:

- **UnifiedChainIndexer** struct with shared provider and postgres client
- **ContractConfig** with address, start_block, and contract type
- **Event routing** that checks contract addresses and deployment blocks
- **Human Points handlers**:
  - Passport mint handler for EAS Attested events (validates schema UID)
  - Human ID SBT handler for Transfer events (checks for mints from zero address)
- **All staking event handlers** ported from the original implementation
- **Robustness features** including timeout detection and automatic recovery
- **Main.rs updated**
  - Replaced all separate indexer spawning with unified indexers
  - Each chain now has a single indexer handling all event types
  - Added unified indexers for all Human Points chains (Base, Linea, Scroll, zkSync, Shape)
  - Human Points contracts conditionally added based on `HUMAN_POINTS_ENABLED` flag
  - Removed the old `run_human_points_indexers` function

### Next Steps
1. **Update main.rs** to use the unified indexer instead of separate indexers ✅ (Completed Dec 2024)
2. **Integration testing** with forked networks
3. **Gradual migration** of production staking indexers

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

## Next Steps

### Phase 1: Build Unified Indexer Structure (Priority 1)
1. **Create `unified_indexer.rs` module**
   - Define `UnifiedChainIndexer` struct with shared WebSocket connection
   - Implement event routing based on contract address
   - Add deployment block checking in each handler

2. **Implement Configuration Structure**
   ```rust
   struct ChainConfig {
       chain_id: u32,
       rpc_url: String,
       staking: Option<ContractConfig>,
       passport_mint: Option<ContractConfig>,
       human_id_mint: Option<ContractConfig>, // Only Optimism
   }
   
   struct ContractConfig {
       address: Address,
       start_block: u64, // Deployment block for this specific contract
       // Additional contract-specific config
   }
   ```

3. **Port Existing Robustness Features**
   - Block tracking and recovery from `staking_indexer.rs`
   - Timeout detection (15-minute no-event warning)
   - Automatic restart on errors
   - Historical block processing

### Phase 2: Implement Human Points Handlers (Priority 2)
1. **Passport Mint Handler**
   - Watch EAS Attested events on specified addresses
   - Validate schema UID matches expected value
   - Extract recipient address and lowercase it
   - Insert PMT action with chain_id

2. **Human ID SBT Handler** (Optimism only)
   - Watch Transfer events from Human ID contract
   - Filter for minting events (from = zero address)
   - Extract recipient address and lowercase it
   - Insert HIM action with chain_id = 10

### Phase 3: Migrate Staking Indexers (Priority 3) ⚠️ PRODUCTION DATA
**CRITICAL**: This phase involves migrating production indexers. Extra care required!

1. **Update each chain's staking handler**
   - Move logic into unified indexer's event router
   - Remove separate staking indexer instances
   - Maintain existing SQL generation logic
   - **MUST preserve all existing block tracking data**
   - **Test thoroughly to ensure no staking events are missed**

2. **Update `main.rs`**
   - Replace multiple indexer spawns with one per chain
   - Simplify error handling with fewer tasks
   - **Consider running both old and new in parallel initially**

### Phase 4: Testing & Deployment
1. **Local Testing**
   - Test with forked networks
   - Verify no events are missed during migration
   - Confirm block tracking works correctly

2. **Staging Deployment**
   - Deploy alongside existing indexers initially
   - Compare outputs to ensure consistency
   - Monitor resource usage improvements

3. **Production Rollout**
   - Gradually migrate chains one at a time
   - Keep old indexers as backup initially
   - Full cutover once confident

### Key Implementation Considerations
- **Backwards Compatibility**: Ensure existing `stake_lastblock` entries work unchanged
- **Deployment Block Filtering**: Each handler must check `event.block >= deployment_block`
- **Error Isolation**: One contract's errors shouldn't affect others on same chain
- **Monitoring**: Add metrics for events processed per contract type

## Recent Implementation Updates

### Critical Fixes Applied
1. **Fixed Chain ID Bug**: Human ID mints were incorrectly hardcoded to use Optimism's chain ID (10). Now correctly uses `self.chain_config.chain_id`.

2. **Consistent Error Handling**: All event types now handle errors consistently - logging errors and continuing rather than crashing the indexer. This prevents one bad event from taking down the entire indexer.

3. **Transaction Support**: Human Points operations now use database transactions with proper BEGIN/COMMIT/ROLLBACK, matching the pattern used for staking events.

4. **WebSocket Reconnection**: Added detection for when the WebSocket stream ends unexpectedly, triggering the indexer's automatic restart mechanism.

5. **Enhanced Event Monitoring**: The 15-minute timeout now monitors BOTH staking and Human Points events (filtering for only PMT and HIM actions). Previously only checked staking events.

### Important Notes for Future Development

#### Event Count Monitoring
The `get_total_event_count` function specifically filters Human Points events to only count PMT and HIM actions:
```sql
SELECT COUNT(*) FROM registry_humanpoints WHERE chain_id = $1 AND action IN ('PMT', 'HIM')
```
This is important because the `registry_humanpoints` table contains other action types that aren't related to on-chain indexing.

#### Error Handling Philosophy
The indexer uses a "log and continue" approach for individual event processing errors. This is intentional because:
- The database has ON CONFLICT DO NOTHING clauses to handle duplicates
- Re-processing events is safe and expected during restarts
- One malformed event shouldn't stop processing of other valid events

#### Deployment Blocks Still Needed
All Human Points contracts currently have `start_block: 0`. These MUST be updated with actual deployment block numbers before production use to avoid scanning from genesis.

#### Cleanup Needed
The `human_points_indexer.rs` module is obsolete and should be removed. The unified indexer architecture has completely replaced it.

#### Transaction Handling Pattern (December 2024 Update)
The Human Points event handlers have been refactored to follow the same pattern as staking events:
- Created `add_human_points_event` method in `postgres.rs` that encapsulates all transaction logic
- This method handles BEGIN/COMMIT/ROLLBACK internally
- Duplicate key errors are gracefully handled (returns Ok for idempotent processing)
- Event handlers (`process_passport_mint_log` and `process_human_id_mint_log`) now simply call this method
- Reduced code duplication by ~160 lines total
- Consistent error handling across all event types

### Testing Recommendations
1. Test with a chain that has both staking and Human Points events to verify the timeout monitoring works correctly
2. Simulate WebSocket disconnections to ensure proper recovery
3. Test transaction rollback scenarios by intentionally causing database errors
4. Verify that other action types in registry_humanpoints don't interfere with event counting
