# Test Plan for Indexer

## Current State
We have a Rust indexer that processes blockchain events and writes them to PostgreSQL. We want to add tests that verify:
- Input: Fake blockchain events
- Output: Correct SQL statements with correct parameters

## The Problem
The `PostgresClient` struct owns a connection pool and gets database clients from it internally. This makes it hard to mock the actual SQL calls.

## Simple Solution
1. Extract SQL generation into pure functions that can be tested without any database connection
2. Test these pure functions directly: event in → SQL string + params out

## Example Structure

```rust
// Extract the event processing + SQL generation into testable functions
pub fn process_self_stake_event(
    event: &SelfStakeFilter,
    chain_id: u32,
    block_number: u64,
    block_timestamp: u64,
    tx_hash: &str,
) -> Vec<SqlCall> {
    // Convert H160 → lowercase hex string
    let staker = format!("{:#x}", event.staker);
    let stakee = staker.clone(); // Self stake: staker == stakee
    
    // Convert u128 → Decimal with 18 decimals
    let mut amount = Decimal::from_u128(event.amount).unwrap();
    amount.set_scale(18).unwrap();
    
    // Convert u64 → DateTime
    let unlock_time = DateTime::from_timestamp(event.unlock_time as i64, 0).unwrap();
    let lock_time = DateTime::from_timestamp(block_timestamp as i64, 0).unwrap();
    
    // Generate SQL calls
    vec![
        SqlCall {
            query: "BEGIN".to_string(),
            params: vec![],
        },
        SqlCall {
            query: "INSERT INTO stake_stakeevent (event_type, chain, staker, stakee, amount, unlock_time, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)".to_string(),
            params: vec![
                "SelfStake".to_string(),
                (chain_id as i32).to_string(),
                staker.clone(),
                stakee.clone(),
                amount.to_string(),
                unlock_time.to_string(),
                block_number.to_string(),
                tx_hash.to_string(),
            ],
        },
        // ... more SQL calls
        SqlCall {
            query: "COMMIT".to_string(),
            params: vec![],
        },
    ]
}

// Test
#[test]
fn test_self_stake_event_full_processing() {
    // Start with the raw event - exactly as it comes from the blockchain
    let event = SelfStakeFilter {
        staker: Address::from_str("0xABCDEF1234567890123456789012345678901234").unwrap(),
        amount: 1_000_000_000_000_000_000u128, // 1 token with 18 decimals
        unlock_time: 1700000000u64,
    };
    
    let sql_calls = process_self_stake_event(&event, 1, 12345, 1699999999, "0xabc123");
    
    // Verify address was lowercased
    assert_eq!(sql_calls[1].params[2], "0xabcdef1234567890123456789012345678901234");
    assert_eq!(sql_calls[1].params[3], "0xabcdef1234567890123456789012345678901234"); // staker == stakee
    
    // Verify amount was converted to decimal with 18 decimals
    assert_eq!(sql_calls[1].params[4], "1.000000000000000000");
    
    // Verify all transformations happened correctly
}
```

## What We Need to Test

### 1. Staking Events
- `SelfStake`: staker == stakee, positive amount
- `CommunityStake`: staker != stakee, positive amount  
- `Slash`: negative amount in stake_stakeevent, UPDATE with negative
- `Release`: positive amount in UPDATE
- `Withdraw` (both types): negative amount in UPDATE

### 2. Human Points (Future)
- Passport mint: 300 points * multiplier
- Human ID mint: 1000 points * multiplier
- Multiplier lookup and application
- Address lowercase conversion
- Deduplication via ON CONFLICT

## Benefits of This Approach
- Pure functions are easy to test
- No async complexity
- No mocking trait bounds issues
- Can verify exact SQL strings and parameter values
- Tests run fast without database

## Next Steps
1. Clean up the existing test mess
2. Extract SQL generation into pure functions
3. Write simple tests: fake event → verify SQL output
4. Later: integration tests with real database if needed