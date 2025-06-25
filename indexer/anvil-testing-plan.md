# Anvil-Based E2E Testing Plan for Indexer

## Overview

This document outlines a comprehensive testing strategy using Anvil (local Ethereum node) to test the indexer end-to-end, from blockchain events to database records. The approach uses a dummy event emitter contract that can emit all the events we need to test, avoiding the complexity of actual contract logic.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Anvil     │────▶│   Indexer    │────▶│  Postgres  │
│ (Local ETH) │     │ (Local prod code) │     │    (DB)    │
└─────────────┘     └──────────────┘     └────────────┘
       │                                          │
       │                                          │
       ▼                                          ▼
┌─────────────┐                          ┌────────────┐
│Test Script  │                          │ Savepoint  │
│(Scenarios)  │                          │ Rollback   │
└─────────────┘                          └────────────┘
```

## Dummy Event Emitter Contract

Instead of deploying and interacting with real staking/EAS/SBT contracts, we use a single dummy contract that can emit all the events we need:

```solidity
// contracts/test/EventEmitter.sol
pragma solidity ^0.8.0;

contract EventEmitter {
    // Staking events
    event SelfStake(address indexed staker, uint256 amount, uint256 unlock_time);
    event CommunityStake(address indexed staker, address indexed stakee, uint256 amount, uint256 unlock_time);
    event Withdraw(address indexed staker, uint256 amount);
    event WithdrawFor(address indexed staker, address indexed stakee, uint256 amount);
    event Slash(address[] users, uint256[] amounts);
    event Release(address indexed user, uint256 amount);
    
    // Human Points events (EAS style)
    event Attested(
        address indexed recipient,
        address indexed attester,
        bytes32 uid,
        bytes32 indexed schemaId
    );
    
    // Human ID SBT events
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    
    // Emit any event on demand
    function emitSelfStake(address staker, uint256 amount, uint256 unlockTime) external {
        emit SelfStake(staker, amount, unlockTime);
    }
    
    function emitCommunityStake(address staker, address stakee, uint256 amount, uint256 unlockTime) external {
        emit CommunityStake(staker, stakee, amount, unlockTime);
    }
    
    function emitWithdraw(address staker, uint256 amount) external {
        emit Withdraw(staker, amount);
    }
    
    function emitSlash(address[] memory users, uint256[] memory amounts) external {
        emit Slash(users, amounts);
    }
    
    function emitPassportAttestation(address recipient, bytes32 uid) external {
        // Passport schema ID from production
        bytes32 schemaId = 0x...;
        emit Attested(recipient, msg.sender, uid, schemaId);
    }
    
    function emitHumanIdMint(address to, uint256 tokenId) external {
        emit Transfer(address(0), to, tokenId);
    }
}
```

## Test Runner Script

```bash
#!/bin/bash
# test-indexer.sh

set -e

# Configuration
DB_URL="${1:-postgresql://user:pass@localhost/testdb}"
ANVIL_PORT="${ANVIL_PORT:-8545}"

echo "🚀 Starting Indexer E2E Tests"

# 1. Start Anvil
echo "Starting Anvil on port $ANVIL_PORT..."
anvil --port $ANVIL_PORT --block-time 1 --silent &
ANVIL_PID=$!
sleep 2

# 2. Deploy event emitter contract
echo "Deploying event emitter..."
EVENT_EMITTER=$(forge create contracts/test/EventEmitter.sol:EventEmitter \
    --rpc-url http://localhost:$ANVIL_PORT \
    --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
    --json | jq -r '.deployedTo')

# 3. Export environment variables for indexer
export DB_URL="$DB_URL"
export RPC_URL_BASE="http://localhost:$ANVIL_PORT"
export STAKING_CONTRACT_BASE="$EVENT_EMITTER"
export EAS_CONTRACT_BASE="$EVENT_EMITTER"
export HUMAN_ID_CONTRACT_BASE="$EVENT_EMITTER"
export START_BLOCK_BASE="0"
export HUMAN_POINTS_ENABLED="true"

# 4. Run test scenarios
echo "Running test scenarios..."
cargo test --test e2e_tests -- --test-threads=1

# 5. Cleanup
kill $ANVIL_PID 2>/dev/null || true
echo "✅ All tests completed!"
```

## Test Infrastructure (Rust)

### `tests/common/mod.rs`
```rust
use std::process::{Child, Command};
use ethers::prelude::*;
use tokio_postgres::Client;

pub struct TestContext {
    pub anvil: AnvilInstance,
    pub event_emitter: EventEmitter,
    pub db_client: Client,
    pub indexer_handle: Option<tokio::task::JoinHandle<()>>,
}

impl TestContext {
    pub async fn new() -> Self {
        // Start Anvil
        let anvil = AnvilInstance::new().await;
        
        // Deploy event emitter contract
        let event_emitter = EventEmitter::deploy(&anvil.endpoint()).await;
        
        // Get DB client with savepoint
        let db_client = setup_test_db().await;
        
        Self {
            anvil,
            event_emitter,
            db_client,
            indexer_handle: None,
        }
    }
    
    pub async fn start_indexer(&mut self) {
        let endpoint = self.anvil.endpoint();
        let db_url = std::env::var("DB_URL").unwrap();
        
        self.indexer_handle = Some(tokio::spawn(async move {
            // Start the actual production indexer
            indexer::run_with_config(Config {
                rpc_url: endpoint,
                db_url,
                // ... other config
            }).await;
        }));
        
        // Wait for indexer to be ready
        tokio::time::sleep(Duration::from_secs(2)).await;
    }
    
    pub async fn cleanup(self) {
        // Abort indexer
        if let Some(handle) = self.indexer_handle {
            handle.abort();
        }
        
        // Rollback DB changes
        self.db_client.execute("ROLLBACK", &[]).await.unwrap();
        
        // Anvil drops automatically
    }
}

pub struct AnvilInstance {
    process: Child,
    port: u16,
}

impl AnvilInstance {
    pub async fn new() -> Self {
        let port = portpicker::pick_unused_port().unwrap();
        
        let process = Command::new("anvil")
            .arg("--port").arg(port.to_string())
            .arg("--block-time").arg("1")
            .arg("--accounts").arg("10")
            .arg("--silent")
            .spawn()
            .expect("Failed to start Anvil");
        
        // Wait for Anvil to be ready
        wait_for_port(port).await;
        
        Self { process, port }
    }
    
    pub fn endpoint(&self) -> String {
        format!("http://localhost:{}", self.port)
    }
}

impl Drop for AnvilInstance {
    fn drop(&mut self) {
        let _ = self.process.kill();
    }
}

async fn setup_test_db() -> Client {
    let db_url = std::env::var("DB_URL")
        .expect("DB_URL must be set for tests");
    
    let (client, connection) = tokio_postgres::connect(&db_url, NoTls)
        .await.unwrap();
    
    tokio::spawn(connection);
    
    // Start transaction with savepoint
    client.execute("BEGIN", &[]).await.unwrap();
    client.execute("SAVEPOINT test_start", &[]).await.unwrap();
    
    client
}
```

### Simple Event Emission Helper
```rust
// tests/common/event_emitter.rs
pub struct EventEmitter {
    contract: ethers::Contract<SignerMiddleware<Provider<Http>, LocalWallet>>,
}

impl EventEmitter {
    pub async fn emit_self_stake(&self, staker: Address, amount: U256, unlock_time: U256) -> Result<()> {
        self.contract
            .method::<_, ()>("emitSelfStake", (staker, amount, unlock_time))?
            .send()
            .await?
            .await?;
        Ok(())
    }
    
    pub async fn emit_withdraw(&self, staker: Address, amount: U256) -> Result<()> {
        self.contract
            .method::<_, ()>("emitWithdraw", (staker, amount))?
            .send()
            .await?
            .await?;
        Ok(())
    }
    
    pub async fn emit_slash(&self, users: Vec<Address>, amounts: Vec<U256>) -> Result<()> {
        self.contract
            .method::<_, ()>("emitSlash", (users, amounts))?
            .send()
            .await?
            .await?;
        Ok(())
    }
    
    // ... other event methods
}
```

### `tests/e2e_tests.rs`
```rust
mod common;
use common::*;

#[tokio::test]
async fn test_self_stake_flow() {
    let mut ctx = TestContext::new().await;
    ctx.start_indexer().await;
    
    // Emit a self-stake event
    let staker = Address::from_str("0x1234567890123456789012345678901234567890").unwrap();
    let amount = U256::from_dec_str("1000000000000000000").unwrap(); // 1 token
    let unlock_time = U256::from(1800000000u64);
    
    ctx.event_emitter
        .emit_self_stake(staker, amount, unlock_time)
        .await.unwrap();
    
    // Wait for indexer to process
    tokio::time::sleep(Duration::from_secs(3)).await;
    
    // Verify database state
    let rows = ctx.db_client
        .query("SELECT * FROM stake_stakeevent WHERE event_type = 'SelfStake'", &[])
        .await.unwrap();
    
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].get::<_, String>("staker"), "0x1234567890123456789012345678901234567890");
    assert_eq!(rows[0].get::<_, rust_decimal::Decimal>("amount").to_string(), "1.000000000000000000");
    
    // Check summary table
    let stake_rows = ctx.db_client
        .query("SELECT * FROM stake_stake", &[])
        .await.unwrap();
    
    assert_eq!(stake_rows.len(), 1);
    assert_eq!(stake_rows[0].get::<_, rust_decimal::Decimal>("amount").to_string(), "1.000000000000000000");
    
    ctx.cleanup().await;
}

#[tokio::test]
async fn test_stake_withdraw_slash_flow() {
    let mut ctx = TestContext::new().await;
    ctx.start_indexer().await;
    
    let staker = Address::from_str("0xaaaa567890123456789012345678901234567890").unwrap();
    let staker2 = Address::from_str("0xbbbb567890123456789012345678901234567890").unwrap();
    
    // 1. Emit self stake event (10 tokens)
    ctx.event_emitter
        .emit_self_stake(staker, U256::from_dec_str("10000000000000000000").unwrap(), U256::from(1800000000u64))
        .await.unwrap();
    
    // 2. Emit community stake event (5 tokens from staker to staker2)
    ctx.event_emitter
        .emit_community_stake(staker, staker2, U256::from_dec_str("5000000000000000000").unwrap(), U256::from(1800000000u64))
        .await.unwrap();
    
    // 3. Emit slash event (2 tokens)
    ctx.event_emitter
        .emit_slash(vec![staker], vec![U256::from_dec_str("2000000000000000000").unwrap()])
        .await.unwrap();
    
    // 4. Emit withdraw event (3 tokens)
    ctx.event_emitter
        .emit_withdraw(staker, U256::from_dec_str("3000000000000000000").unwrap())
        .await.unwrap();
    
    // Wait for processing
    tokio::time::sleep(Duration::from_secs(5)).await;
    
    // Verify final state
    let final_stake = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $1", 
            &[&"0xaaaa567890123456789012345678901234567890"]
        )
        .await.unwrap();
    
    // Started with 10, slashed 2, withdrew 3 = 5 remaining
    assert_eq!(
        final_stake.get::<_, rust_decimal::Decimal>("amount").to_string(), 
        "5.000000000000000000"
    );
    
    ctx.cleanup().await;
}

#[tokio::test]
async fn test_indexer_recovery_after_crash() {
    let mut ctx = TestContext::new().await;
    
    // Start indexer
    ctx.start_indexer().await;
    
    // Emit some events
    for i in 0..5 {
        let staker = Address::from_str(&format!("0x{:040x}", i + 1)).unwrap();
        ctx.event_emitter
            .emit_self_stake(staker, U256::from_dec_str("1000000000000000000").unwrap(), U256::from(1800000000u64))
            .await.unwrap();
    }
    
    tokio::time::sleep(Duration::from_secs(3)).await;
    
    // Kill indexer
    ctx.indexer_handle.take().unwrap().abort();
    
    // Emit more events while indexer is down
    for i in 5..10 {
        let staker = Address::from_str(&format!("0x{:040x}", i + 1)).unwrap();
        ctx.event_emitter
            .emit_self_stake(staker, U256::from_dec_str("1000000000000000000").unwrap(), U256::from(1800000000u64))
            .await.unwrap();
    }
    
    // Restart indexer
    ctx.start_indexer().await;
    
    // Wait for catch-up
    tokio::time::sleep(Duration::from_secs(5)).await;
    
    // Verify all 10 events were processed
    let count = ctx.db_client
        .query_one("SELECT COUNT(*) FROM stake_stakeevent", &[])
        .await.unwrap()
        .get::<_, i64>(0);
    
    assert_eq!(count, 10);
    
    ctx.cleanup().await;
}

#[tokio::test] 
async fn test_human_points_minting() {
    let mut ctx = TestContext::new().await;
    ctx.start_indexer().await;
    
    let recipient = Address::from_str("0xcccc567890123456789012345678901234567890").unwrap();
    
    // Emit passport attestation event (300 points)
    ctx.event_emitter
        .emit_passport_attestation(recipient, H256::random())
        .await.unwrap();
    
    // Emit Human ID mint event (1000 points)  
    ctx.event_emitter
        .emit_human_id_mint(recipient, U256::from(12345))
        .await.unwrap();
    
    tokio::time::sleep(Duration::from_secs(3)).await;
    
    // Verify points
    let points = ctx.db_client
        .query("SELECT * FROM registry_humanpoints ORDER BY created_at", &[])
        .await.unwrap();
    
    assert_eq!(points.len(), 2);
    assert_eq!(points[0].get::<_, i32>("points"), 300);
    assert_eq!(points[0].get::<_, String>("action"), "passport");
    assert_eq!(points[1].get::<_, i32>("points"), 1000);
    assert_eq!(points[1].get::<_, String>("action"), "humanity");
    
    ctx.cleanup().await;
}
```

## Test Scenarios

### Basic Scenarios
1. **Single stake → withdraw flow**
2. **Multiple stakers interaction**
3. **Slash events and balance updates**
4. **Release events**
5. **Human points minting (passport + SBT)**

### Edge Cases
1. **Duplicate transactions** (idempotency)
2. **Reorg handling** (if we add it)
3. **Indexer crash and recovery**
4. **Events in same block**
5. **Historical sync from specific block**

## Lightweight Unit Tests

For unit tests that add value beyond type checking:

### `src/utils.rs` tests
```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_decimal_conversion_precision() {
        // This matters because we need exact decimal representation
        let amounts = vec![
            ("1", "1.000000000000000000"),
            ("1000000000000000000", "1.000000000000000000"),
            ("1500000000000000000", "1.500000000000000000"),
            ("999999999999999999", "0.999999999999999999"),
            ("1000000000000000001", "1.000000000000000001"),
        ];
        
        for (wei, expected) in amounts {
            let mut decimal = Decimal::from_str(wei).unwrap();
            decimal.set_scale(18).unwrap();
            assert_eq!(decimal.to_string(), expected);
        }
    }
    
    #[test]
    fn test_stake_amount_operation() {
        // Critical business logic
        let test_cases = vec![
            (StakeEventType::SelfStake, StakeAmountOperation::Add),
            (StakeEventType::CommunityStake, StakeAmountOperation::Add),
            (StakeEventType::Slash, StakeAmountOperation::Subtract),
            (StakeEventType::Withdraw, StakeAmountOperation::Subtract),
            (StakeEventType::WithdrawInBatch, StakeAmountOperation::Subtract),
            (StakeEventType::Release, StakeAmountOperation::Add),
        ];
        
        for (event_type, expected_op) in test_cases {
            assert_eq!(
                StakeAmountOperation::from_event_type(&event_type),
                expected_op
            );
        }
    }
}
```

### `src/postgres.rs` tests
```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_duplicate_key_error_detection() {
        // Important for idempotency handling
        let error_msg = "duplicate key value violates unique constraint \"stake_stakeevent_tx_hash_chain_stakee_key\"";
        assert!(is_duplicate_key_error(error_msg));
        
        let other_error = "connection refused";
        assert!(!is_duplicate_key_error(other_error));
    }
    
    #[test]
    fn test_block_range_calculation() {
        // Critical for historical sync
        assert_eq!(calculate_block_range(0, 10000, 1000), vec![
            (0, 999),
            (1000, 1999),
            (2000, 2999),
            // ... etc
        ]);
        
        // Edge case: non-divisible range
        assert_eq!(calculate_block_range(0, 1500, 1000), vec![
            (0, 999),
            (1000, 1500),
        ]);
    }
}
```

## CI Integration

```yaml
# .github/workflows/test.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Foundry
        uses: foundry-rs/foundry-toolchain@v1
        
      - name: Setup test database
        run: |
          psql -h localhost -U postgres -c "CREATE DATABASE indexer_test;"
          psql -h localhost -U postgres -d indexer_test -f schema.sql
        env:
          PGPASSWORD: postgres
          
      - name: Run E2E tests
        run: ./test-indexer.sh "postgresql://postgres:postgres@localhost/indexer_test"
        
      - name: Run unit tests
        run: cargo test --lib
```

## Benefits of Event Emitter Approach

Using a dummy event emitter contract instead of real contracts provides:

1. **Library Independence** - Tests aren't tied to ethers.rs contract abstractions
2. **Simplicity** - Just emit events, no complex contract state or logic
3. **Flexibility** - Easy to emit invalid/edge-case events for testing
4. **Speed** - No need to deploy multiple complex contracts
5. **Focus** - Tests the indexer, not the contracts

## Alternative: Raw Transaction Approach

For even more library independence, you could send raw transactions that emit events:

```rust
// Send raw transaction that emits a SelfStake event
let tx = TransactionRequest::new()
    .to(event_emitter_address)
    .data(encode_function_call("emitSelfStake", [staker, amount, unlock_time]))
    .send()
    .await?;
```

This approach works with any Ethereum client library.

## Summary

This approach gives us:
1. **Real blockchain behavior** - Actual events on actual blockchain
2. **Database isolation** - Each test runs in a savepoint
3. **Fast feedback** - Anvil starts in <1s, single contract deployment
4. **Library agnostic** - Not tied to specific Ethereum library APIs
5. **CI-friendly** - Runs anywhere with Anvil installed

The combination of:
- Lightweight unit tests for critical logic (decimal precision, business rules)
- Anvil E2E tests for full integration testing
- Dummy event emitter for simple, focused testing

Provides comprehensive coverage while keeping tests maintainable and fast.
