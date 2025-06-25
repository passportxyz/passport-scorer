mod common;
use common::*;
use rust_decimal::Decimal;
use std::str::FromStr;

#[tokio::test]
async fn test_self_stake_flow() -> Result<(), Box<dyn std::error::Error>> {
    let mut ctx = TestContext::new().await?;
    
    // Emit a self-stake event
    let staker = Address::from_str("0x1234567890123456789012345678901234567890")?;
    let amount = parse_ether("1")?; // 1 token
    let unlock_time = U256::from(1800000000u64);
    
    ctx.staking_emitter
        .emit_self_stake(staker, amount, unlock_time)
        .await?;
    
    // Wait for indexer to process
    ctx.wait_for_indexer(std::time::Duration::from_secs(3)).await;
    
    // Verify database state
    let rows = ctx.db_client
        .query("SELECT * FROM stake_stakeevent WHERE event_type = 'SelfStake'", &[])
        .await?;
    
    assert_eq!(rows.len(), 1);
    let staker_db: String = rows[0].get("staker");
    assert_eq!(staker_db.to_lowercase(), "0x1234567890123456789012345678901234567890");
    
    let amount_db: Decimal = rows[0].get("amount");
    assert_eq!(amount_db.to_string(), "1.000000000000000000");
    
    // Check summary table
    let stake_rows = ctx.db_client
        .query("SELECT * FROM stake_stake", &[])
        .await?;
    
    assert_eq!(stake_rows.len(), 1);
    let stake_amount: Decimal = stake_rows[0].get("amount");
    assert_eq!(stake_amount.to_string(), "1.000000000000000000");
    
    ctx.cleanup().await?;
    Ok(())
}

#[tokio::test]
async fn test_stake_withdraw_slash_flow() -> Result<(), Box<dyn std::error::Error>> {
    let mut ctx = TestContext::new().await?;
    
    let staker = Address::from_str("0xaaaa567890123456789012345678901234567890")?;
    let staker2 = Address::from_str("0xbbbb567890123456789012345678901234567890")?;
    
    // 1. Emit self stake event (10 tokens)
    ctx.staking_emitter
        .emit_self_stake(staker, parse_ether("10")?, U256::from(1800000000u64))
        .await?;
    
    // 2. Emit community stake event (5 tokens from staker to staker2)
    ctx.staking_emitter
        .emit_community_stake(staker, staker2, parse_ether("5")?, U256::from(1800000000u64))
        .await?;
    
    // 3. Emit slash event (2 tokens)
    ctx.staking_emitter
        .emit_slash(vec![staker], vec![parse_ether("2")?])
        .await?;
    
    // 4. Emit withdraw event (3 tokens)
    ctx.staking_emitter
        .emit_withdraw(staker, parse_ether("3")?)
        .await?;
    
    // Wait for processing
    ctx.wait_for_indexer(std::time::Duration::from_secs(5)).await;
    
    // Verify final state
    let final_stake = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $1", 
            &[&"0xaaaa567890123456789012345678901234567890"]
        )
        .await?;
    
    // Started with 10, slashed 2, withdrew 3 = 5 remaining
    let final_amount: Decimal = final_stake.get("amount");
    assert_eq!(final_amount.to_string(), "5.000000000000000000");
    
    // Check community stake is still there
    let community_stake = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $2", 
            &[&"0xaaaa567890123456789012345678901234567890", &"0xbbbb567890123456789012345678901234567890"]
        )
        .await?;
    
    let community_amount: Decimal = community_stake.get("amount");
    assert_eq!(community_amount.to_string(), "5.000000000000000000");
    
    ctx.cleanup().await?;
    Ok(())
}

#[tokio::test]
async fn test_batch_withdraw_events() -> Result<(), Box<dyn std::error::Error>> {
    let mut ctx = TestContext::new().await?;
    
    let staker1 = Address::from_str("0x1111111111111111111111111111111111111111")?;
    let staker2 = Address::from_str("0x2222222222222222222222222222222222222222")?;
    let stakee1 = Address::from_str("0x3333333333333333333333333333333333333333")?;
    let stakee2 = Address::from_str("0x4444444444444444444444444444444444444444")?;
    
    // Setup: Create community stakes
    ctx.staking_emitter
        .emit_community_stake(staker1, stakee1, parse_ether("10")?, U256::from(1800000000u64))
        .await?;
    ctx.staking_emitter
        .emit_community_stake(staker2, stakee2, parse_ether("20")?, U256::from(1800000000u64))
        .await?;
    
    // Wait for initial stakes to be processed
    ctx.wait_for_indexer(std::time::Duration::from_secs(3)).await;
    
    // Emit batch withdraw
    ctx.staking_emitter
        .emit_withdraw_in_batch(
            vec![staker1, staker2],
            vec![stakee1, stakee2],
            vec![parse_ether("5")?, parse_ether("10")?]
        )
        .await?;
    
    // Wait for processing
    ctx.wait_for_indexer(std::time::Duration::from_secs(3)).await;
    
    // Verify final amounts
    let stake1 = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $2", 
            &[&"0x1111111111111111111111111111111111111111", &"0x3333333333333333333333333333333333333333"]
        )
        .await?;
    
    let amount1: Decimal = stake1.get("amount");
    assert_eq!(amount1.to_string(), "5.000000000000000000");
    
    let stake2 = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $2", 
            &[&"0x2222222222222222222222222222222222222222", &"0x4444444444444444444444444444444444444444"]
        )
        .await?;
    
    let amount2: Decimal = stake2.get("amount");
    assert_eq!(amount2.to_string(), "10.000000000000000000");
    
    ctx.cleanup().await?;
    Ok(())
}

#[tokio::test]
async fn test_indexer_processes_all_events() -> Result<(), Box<dyn std::error::Error>> {
    // This test verifies the indexer processes events correctly
    // Note: We can't test crash recovery in this setup since the indexer
    // is managed by the test script, not individual tests
    
    let mut ctx = TestContext::new().await?;
    
    // Emit a batch of events
    for i in 0..10 {
        let staker = Address::from_str(&format!("0x{:040x}", i + 1))?;
        ctx.staking_emitter
            .emit_self_stake(staker, parse_ether("1")?, U256::from(1800000000u64))
            .await?;
    }
    
    // Wait for indexer to process
    ctx.wait_for_indexer(std::time::Duration::from_secs(5)).await;
    
    // Verify all 10 events were processed
    let count: i64 = ctx.db_client
        .query_one("SELECT COUNT(*) FROM stake_stakeevent WHERE event_type = 'SelfStake'", &[])
        .await?
        .get(0);
    
    assert_eq!(count, 10);
    
    // Verify the stake summary table is also updated
    let stake_count: i64 = ctx.db_client
        .query_one("SELECT COUNT(*) FROM stake_stake", &[])
        .await?
        .get(0);
    
    assert_eq!(stake_count, 10);
    
    ctx.cleanup().await?;
    Ok(())
}

#[tokio::test] 
async fn test_human_points_minting() -> Result<(), Box<dyn std::error::Error>> {
    let mut ctx = TestContext::new().await?;
    
    let recipient = Address::from_str("0xcccc567890123456789012345678901234567890")?;
    
    // Emit passport attestation event (300 points) from EAS contract
    ctx.eas_emitter
        .emit_passport_attestation(recipient, H256::random(), U256::from(10)) // Optimism chain ID
        .await?;
    
    // Emit Human ID mint event (1000 points) from Human ID contract
    ctx.human_id_emitter
        .emit_human_id_mint(recipient, U256::from(12345))
        .await?;
    
    ctx.wait_for_indexer(std::time::Duration::from_secs(3)).await;
    
    // Verify points
    let points = ctx.db_client
        .query("SELECT * FROM registry_humanpoints ORDER BY timestamp", &[])
        .await?;
    
    assert_eq!(points.len(), 2);
    
    let points1: i32 = points[0].get("points");
    let action1: String = points[0].get("action");
    assert_eq!(points1, 300);
    assert_eq!(action1, "passport");
    
    let points2: i32 = points[1].get("points");
    let action2: String = points[1].get("action");
    assert_eq!(points2, 1000);
    assert_eq!(action2, "humanity");
    
    ctx.cleanup().await?;
    Ok(())
}

#[tokio::test]
async fn test_duplicate_transaction_handling() -> Result<(), Box<dyn std::error::Error>> {
    let mut ctx = TestContext::new().await?;
    
    let staker = Address::from_str("0xdead567890123456789012345678901234567890")?;
    let amount = parse_ether("5")?;
    let unlock_time = U256::from(1800000000u64);
    
    // Emit the same event twice
    let _receipt1 = ctx.staking_emitter
        .emit_self_stake(staker, amount, unlock_time)
        .await?;
    
    // Wait for first event to be processed
    ctx.wait_for_indexer(std::time::Duration::from_secs(2)).await;
    
    // Manually emit the same event again (simulating a reorg or duplicate)
    // In a real scenario, this would be the same transaction hash
    let _receipt2 = ctx.staking_emitter
        .emit_self_stake(staker, amount, unlock_time)
        .await?;
    
    ctx.wait_for_indexer(std::time::Duration::from_secs(2)).await;
    
    // Verify we have 2 different events (different tx hashes)
    let events = ctx.db_client
        .query(
            "SELECT DISTINCT tx_hash FROM stake_stakeevent WHERE staker = $1", 
            &[&"0xdead567890123456789012345678901234567890"]
        )
        .await?;
    
    assert_eq!(events.len(), 2); // Two different transactions
    
    // But the stake amount should be correct (10 total)
    let stake = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $1", 
            &[&"0xdead567890123456789012345678901234567890"]
        )
        .await?;
    
    let total_amount: Decimal = stake.get("amount");
    assert_eq!(total_amount.to_string(), "10.000000000000000000");
    
    ctx.cleanup().await?;
    Ok(())
}

#[tokio::test]
async fn test_release_event_handling() -> Result<(), Box<dyn std::error::Error>> {
    let mut ctx = TestContext::new().await?;
    
    let user = Address::from_str("0xbeef567890123456789012345678901234567890")?;
    
    // First stake some tokens
    ctx.staking_emitter
        .emit_self_stake(user, parse_ether("10")?, U256::from(1800000000u64))
        .await?;
    
    // Then slash some
    ctx.staking_emitter
        .emit_slash(vec![user], vec![parse_ether("5")?])
        .await?;
    
    ctx.wait_for_indexer(std::time::Duration::from_secs(3)).await;
    
    // Verify slashed amount
    let stake_after_slash = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $1", 
            &[&"0xbeef567890123456789012345678901234567890"]
        )
        .await?;
    
    let amount_after_slash: Decimal = stake_after_slash.get("amount");
    assert_eq!(amount_after_slash.to_string(), "5.000000000000000000");
    
    // Now release some tokens back
    ctx.staking_emitter
        .emit_release(user, parse_ether("3")?)
        .await?;
    
    ctx.wait_for_indexer(std::time::Duration::from_secs(3)).await;
    
    // Verify final amount
    let final_stake = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $1", 
            &[&"0xbeef567890123456789012345678901234567890"]
        )
        .await?;
    
    let final_amount: Decimal = final_stake.get("amount");
    assert_eq!(final_amount.to_string(), "8.000000000000000000");
    
    // Check event history
    let events = ctx.db_client
        .query(
            "SELECT event_type, amount FROM stake_stakeevent WHERE staker = $1 ORDER BY block_number", 
            &[&"0xbeef567890123456789012345678901234567890"]
        )
        .await?;
    
    assert_eq!(events.len(), 3);
    
    let event_types: Vec<String> = events.iter().map(|row| row.get("event_type")).collect();
    assert_eq!(event_types, vec!["SelfStake", "Slash", "Release"]);
    
    ctx.cleanup().await?;
    Ok(())
}

#[tokio::test]
async fn test_events_in_same_block() -> Result<(), Box<dyn std::error::Error>> {
    let mut ctx = TestContext::new().await?;
    
    let staker = Address::from_str("0xface567890123456789012345678901234567890")?;
    
    // Disable auto-mining to batch transactions in same block
    let _ = ctx.provider
        .request::<_, ()>("evm_setAutomine", [false])
        .await?;
    
    // Send multiple transactions
    let _ = ctx.staking_emitter
        .emit_self_stake(staker, parse_ether("5")?, U256::from(1800000000u64))
        .await?;
    
    let _ = ctx.staking_emitter
        .emit_withdraw(staker, parse_ether("2")?)
        .await?;
    
    let _ = ctx.staking_emitter
        .emit_self_stake(staker, parse_ether("3")?, U256::from(1900000000u64))
        .await?;
    
    // Mine all transactions in one block
    let _ = ctx.provider
        .request::<_, ()>("evm_mine", Vec::<String>::new())
        .await?;
    
    // Re-enable auto-mining
    let _ = ctx.provider
        .request::<_, ()>("evm_setAutomine", [true])
        .await?;
    
    // Wait for indexer to process
    ctx.wait_for_indexer(std::time::Duration::from_secs(3)).await;
    
    // Verify all events are in the same block
    let events = ctx.db_client
        .query(
            "SELECT block_number, event_type FROM stake_stakeevent WHERE staker = $1 ORDER BY log_index", 
            &[&"0xface567890123456789012345678901234567890"]
        )
        .await?;
    
    assert_eq!(events.len(), 3);
    
    // All should have same block number
    let block_numbers: Vec<i64> = events.iter().map(|row| row.get("block_number")).collect();
    assert!(block_numbers.iter().all(|&bn| bn == block_numbers[0]));
    
    // Final stake should be: 5 - 2 + 3 = 6
    let final_stake = ctx.db_client
        .query_one(
            "SELECT amount FROM stake_stake WHERE staker = $1 AND stakee = $1", 
            &[&"0xface567890123456789012345678901234567890"]
        )
        .await?;
    
    let final_amount: Decimal = final_stake.get("amount");
    assert_eq!(final_amount.to_string(), "6.000000000000000000");
    
    ctx.cleanup().await?;
    Ok(())
}
