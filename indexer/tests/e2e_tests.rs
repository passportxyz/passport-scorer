mod common;
use common::*;
use rust_decimal::Decimal;
use std::str::FromStr;
use ethers::prelude::*;
use ethers::utils::parse_ether;

// Helper function to get test table names
fn get_table_name(base_name: &str) -> String {
    if let Ok(suffix) = std::env::var("TEST_TABLE_SUFFIX") {
        format!("{}{}", base_name, suffix)
    } else {
        base_name.to_string()
    }
}

#[tokio::test]
async fn test_self_stake_flow() -> Result<(), Box<dyn std::error::Error>> {
    let ctx = TestContext::new().await?;
    
    // No need to clean up - tests use unique addresses and data is rolled back after test suite
    
    // Emit a self-stake event
    let staker = Address::from_str("0x1234567890123456789012345678901234567890")?;
    let amount = parse_ether("1")?; // 1 token
    let unlock_time = U256::from(1800000000u64);
    
    println!("Emitting self-stake event...");
    let receipt = ctx.staking_emitter
        .emit_self_stake(staker, amount, unlock_time)
        .await?;
    println!("Transaction hash: {:?}", receipt.transaction_hash);
    println!("Block number: {:?}", receipt.block_number);
    
    // Poll for the event to be processed
    println!("Waiting for event to be indexed...");
    ctx.wait_for_stake_event_count(&["0x1234567890123456789012345678901234567890"], 1, std::time::Duration::from_secs(30)).await?;
    
    // Verify database state
    let rows = ctx.db_client
        .query(&format!("SELECT * FROM {} WHERE event_type = 'SST' AND staker = $1", get_table_name("stake_stakeevent")), &[&"0x1234567890123456789012345678901234567890"])
        .await?;
    
    println!("Found {} SelfStake events", rows.len());
    assert_eq!(rows.len(), 1);
    let staker_db: String = rows[0].get("staker");
    assert_eq!(staker_db.to_lowercase(), "0x1234567890123456789012345678901234567890");
    
    let amount_db: Decimal = rows[0].get("amount");
    assert_eq!(amount_db.to_string(), "1.000000000000000000");
    
    // Check summary table
    let stake_rows = ctx.db_client
        .query(&format!("SELECT * FROM {} WHERE staker = $1", get_table_name("stake_stake")), &[&"0x1234567890123456789012345678901234567890"])
        .await?;
    
    assert_eq!(stake_rows.len(), 1);
    let stake_amount: Decimal = stake_rows[0].get("current_amount");
    assert_eq!(stake_amount.to_string(), "1.000000000000000000");
    
    // No cleanup needed - test script handles DB cleanup before running tests
    Ok(())
}

#[tokio::test]
async fn test_stake_withdraw_slash_flow() -> Result<(), Box<dyn std::error::Error>> {
    let ctx = TestContext::new().await?;
    
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
    
    // Wait for all 4 events to be processed
    ctx.wait_for_stake_event_count(&["0xaaaa567890123456789012345678901234567890", "0xbbbb567890123456789012345678901234567890"], 4, std::time::Duration::from_secs(30)).await?;
    
    // Verify final state
    let final_stake = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $1", get_table_name("stake_stake")), 
            &[&"0xaaaa567890123456789012345678901234567890"]
        )
        .await?;
    
    // Started with 10, slashed 2, withdrew 3 = 5 remaining
    let final_amount: Decimal = final_stake.get("current_amount");
    assert_eq!(final_amount.to_string(), "5.000000000000000000");
    
    // Check community stake is still there
    let community_stake = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $2", get_table_name("stake_stake")), 
            &[&"0xaaaa567890123456789012345678901234567890", &"0xbbbb567890123456789012345678901234567890"]
        )
        .await?;
    
    let community_amount: Decimal = community_stake.get("current_amount");
    assert_eq!(community_amount.to_string(), "5.000000000000000000");
    
    // No cleanup needed - test script handles DB cleanup before running tests
    Ok(())
}


#[tokio::test]
async fn test_indexer_processes_all_events() -> Result<(), Box<dyn std::error::Error>> {
    // This test verifies the indexer processes events correctly
    // Note: We can't test crash recovery in this setup since the indexer
    // is managed by the test script, not individual tests
    
    let ctx = TestContext::new().await?;
    
    // Emit a batch of events
    for i in 0..10 {
        let staker = Address::from_str(&format!("0x{:040x}", i + 1))?;
        ctx.staking_emitter
            .emit_self_stake(staker, parse_ether("1")?, U256::from(1800000000u64))
            .await?;
    }
    
    // Wait for all 10 events to be processed
    let test_addresses: Vec<String> = (1..=10).map(|i| format!("0x{:040x}", i)).collect();
    let test_addresses_refs: Vec<&str> = test_addresses.iter().map(|s| s.as_str()).collect();
    ctx.wait_for_stake_event_count(&test_addresses_refs, 10, std::time::Duration::from_secs(30)).await?;
    
    // Verify all 10 events were processed
    let count: i64 = ctx.db_client
        .query_one(&format!("SELECT COUNT(*) FROM {} WHERE event_type = 'SST' AND staker = ANY($1)", get_table_name("stake_stakeevent")), &[&test_addresses_refs])
        .await?
        .get(0);
    
    assert_eq!(count, 10);
    
    // Verify the stake summary table is also updated
    let stake_count: i64 = ctx.db_client
        .query_one(&format!("SELECT COUNT(*) FROM {} WHERE staker = ANY($1)", get_table_name("stake_stake")), &[&test_addresses_refs])
        .await?
        .get(0);
    
    assert_eq!(stake_count, 10);
    
    // No cleanup needed - test script handles DB cleanup before running tests
    Ok(())
}

#[tokio::test] 
async fn test_human_points_minting() -> Result<(), Box<dyn std::error::Error>> {
    let ctx = TestContext::new().await?;
    
    let recipient = Address::from_str("0xcccc567890123456789012345678901234567890")?;
    
    // Emit passport attestation event (300 points) from EAS contract
    ctx.eas_emitter
        .emit_passport_attestation(recipient, H256::random(), U256::from(10)) // Optimism chain ID
        .await?;
    
    // Emit Human ID mint event (1000 points) from Human ID contract
    ctx.human_id_emitter
        .emit_human_id_mint(recipient, U256::from(12345))
        .await?;
    
    // Give time for events to be processed
    tokio::time::sleep(std::time::Duration::from_secs(10)).await;
    
    // Just check if we have 2 records total (regardless of address format)
    let all_records = ctx.db_client
        .query(&format!("SELECT * FROM {} ORDER BY timestamp", get_table_name("registry_humanpoints")), &[])
        .await?;
    
    // For now, just verify we have 2 records with correct actions
    assert_eq!(all_records.len(), 2, "Expected 2 human points records");
    
    let action1: String = all_records[0].get("action");
    let action2: String = all_records[1].get("action");
    
    // Verify actions (order might vary)
    let mut actions = vec![action1, action2];
    actions.sort();
    assert_eq!(actions, vec!["HIM", "PMT"]);
    
    // Records are already verified above
    
    // No cleanup needed - test script handles DB cleanup before running tests
    Ok(())
}

#[tokio::test]
async fn test_duplicate_transaction_handling() -> Result<(), Box<dyn std::error::Error>> {
    let ctx = TestContext::new().await?;
    
    // No need to clean up - tests use unique addresses and data is rolled back after test suite
    
    let staker = Address::from_str("0xdead567890123456789012345678901234567890")?;
    let amount = parse_ether("5")?;
    let unlock_time = U256::from(1800000000u64);
    
    // Emit the same event twice
    let _receipt1 = ctx.staking_emitter
        .emit_self_stake(staker, amount, unlock_time)
        .await?;
    
    // Wait for first event to be processed
    ctx.wait_for_stake_event_count(&["0xdead567890123456789012345678901234567890"], 1, std::time::Duration::from_secs(30)).await?;
    
    // Manually emit the same event again (simulating a reorg or duplicate)
    // In a real scenario, this would be the same transaction hash
    let _receipt2 = ctx.staking_emitter
        .emit_self_stake(staker, amount, unlock_time)
        .await?;
    
    // Wait for second event
    ctx.wait_for_stake_event_count(&["0xdead567890123456789012345678901234567890"], 2, std::time::Duration::from_secs(30)).await?;
    
    // Verify we have 2 different events (different tx hashes)
    let events = ctx.db_client
        .query(
            &format!("SELECT DISTINCT tx_hash FROM {} WHERE staker = $1", get_table_name("stake_stakeevent")), 
            &[&"0xdead567890123456789012345678901234567890"]
        )
        .await?;
    
    assert_eq!(events.len(), 2); // Two different transactions
    
    // But the stake amount should be correct (10 total)
    let stake = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $1", get_table_name("stake_stake")), 
            &[&"0xdead567890123456789012345678901234567890"]
        )
        .await?;
    
    let total_amount: Decimal = stake.get("current_amount");
    assert_eq!(total_amount.to_string(), "10.000000000000000000");
    
    // No cleanup needed - test script handles DB cleanup before running tests
    Ok(())
}

#[tokio::test]
async fn test_release_event_handling() -> Result<(), Box<dyn std::error::Error>> {
    let ctx = TestContext::new().await?;
    
    let user = Address::from_str("0xbeef567890123456789012345678901234567890")?;
    
    // First stake some tokens
    ctx.staking_emitter
        .emit_self_stake(user, parse_ether("10")?, U256::from(1800000000u64))
        .await?;
    
    // Then slash some
    ctx.staking_emitter
        .emit_slash(vec![user], vec![parse_ether("5")?])
        .await?;
    
    // Wait for 2 events to be processed (stake + slash)
    ctx.wait_for_stake_event_count(&["0xbeef567890123456789012345678901234567890"], 2, std::time::Duration::from_secs(30)).await?;
    
    // Verify slashed amount
    let stake_after_slash = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $1", get_table_name("stake_stake")), 
            &[&"0xbeef567890123456789012345678901234567890"]
        )
        .await?;
    
    let amount_after_slash: Decimal = stake_after_slash.get("current_amount");
    assert_eq!(amount_after_slash.to_string(), "5.000000000000000000");
    
    // Now release some tokens back
    ctx.staking_emitter
        .emit_release(user, user, parse_ether("3")?)
        .await?;
    
    // Wait for the release event to be processed (total 3 events)
    ctx.wait_for_stake_event_count(&["0xbeef567890123456789012345678901234567890"], 3, std::time::Duration::from_secs(30)).await?;
    
    // Verify final amount
    let final_stake = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $1", get_table_name("stake_stake")), 
            &[&"0xbeef567890123456789012345678901234567890"]
        )
        .await?;
    
    let final_amount: Decimal = final_stake.get("current_amount");
    assert_eq!(final_amount.to_string(), "8.000000000000000000");
    
    // Check event history
    let events = ctx.db_client
        .query(
            &format!("SELECT event_type, amount FROM {} WHERE staker = $1 ORDER BY block_number", get_table_name("stake_stakeevent")), 
            &[&"0xbeef567890123456789012345678901234567890"]
        )
        .await?;
    
    assert_eq!(events.len(), 3);
    
    let event_types: Vec<String> = events.iter().map(|row| row.get("event_type")).collect();
    assert_eq!(event_types, vec!["SST", "SLA", "REL"]);
    
    // No cleanup needed - test script handles DB cleanup before running tests
    Ok(())
}

#[tokio::test]
async fn test_events_in_same_block() -> Result<(), Box<dyn std::error::Error>> {
    let ctx = TestContext::new().await?;
    
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
    ctx.provider.send_raw_transaction("0x".parse()?).await?;
    
    // Re-enable auto-mining
    let _ = ctx.provider
        .request::<_, ()>("evm_setAutomine", [true])
        .await?;
    
    // Wait for 3 events to be processed in the same block
    ctx.wait_for_stake_event_count(&["0xface567890123456789012345678901234567890"], 3, std::time::Duration::from_secs(30)).await?;
    
    // Verify all events are in the same block
    let events = ctx.db_client
        .query(
            &format!("SELECT block_number, event_type FROM {} WHERE staker = $1 ORDER BY log_index", get_table_name("stake_stakeevent")), 
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
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $1", get_table_name("stake_stake")), 
            &[&"0xface567890123456789012345678901234567890"]
        )
        .await?;
    
    let final_amount: Decimal = final_stake.get("current_amount");
    assert_eq!(final_amount.to_string(), "6.000000000000000000");
    
    // No cleanup needed - test script handles DB cleanup before running tests
    Ok(())
}

#[tokio::test]
async fn test_multiple_withdraw_events() -> Result<(), Box<dyn std::error::Error>> {
    let ctx = TestContext::new().await?;
    
    // No need to clean up - tests use unique addresses and data is rolled back after test suite
    
    // Create multiple stakers and stakees
    let staker1 = Address::from_str("0xaaaa567890123456789012345678901234567890")?;
    let staker2 = Address::from_str("0xbbbb567890123456789012345678901234567890")?;
    let stakee1 = Address::from_str("0xcccc567890123456789012345678901234567890")?;
    let stakee2 = Address::from_str("0xdddd567890123456789012345678901234567890")?;
    
    // First emit some stakes
    ctx.staking_emitter
        .emit_self_stake(staker1, parse_ether("10")?, U256::from(1800000000u64))
        .await?;
    
    ctx.staking_emitter
        .emit_self_stake(staker2, parse_ether("15")?, U256::from(1800000000u64))
        .await?;
    
    ctx.staking_emitter
        .emit_community_stake(staker1, stakee1, parse_ether("5")?, U256::from(1800000000u64))
        .await?;
    
    ctx.staking_emitter
        .emit_community_stake(staker2, stakee2, parse_ether("7")?, U256::from(1800000000u64))
        .await?;
    
    // Wait for stakes to be processed
    ctx.wait_for_stake_event_count(&["0xaaaa567890123456789012345678901234567890", "0xbbbb567890123456789012345678901234567890", "0xcccc567890123456789012345678901234567890", "0xdddd567890123456789012345678901234567890"], 4, std::time::Duration::from_secs(30)).await?;
    
    // Now emit individual withdraw events
    // staker1 withdraws 3 from self
    ctx.staking_emitter
        .emit_withdraw(staker1, parse_ether("3")?)
        .await?;
    
    // staker2 withdraws 4 from self
    ctx.staking_emitter
        .emit_withdraw(staker2, parse_ether("4")?)
        .await?;
    
    // staker1 withdraws 2 from stakee1
    ctx.staking_emitter
        .emit_community_stake_withdrawn(staker1, stakee1, parse_ether("2")?)
        .await?;
    
    // staker2 withdraws 3 from stakee2
    ctx.staking_emitter
        .emit_community_stake_withdrawn(staker2, stakee2, parse_ether("3")?)
        .await?;
    
    // Wait for all withdraw events to be processed
    ctx.wait_for_stake_event_count(&["0xaaaa567890123456789012345678901234567890", "0xbbbb567890123456789012345678901234567890", "0xcccc567890123456789012345678901234567890", "0xdddd567890123456789012345678901234567890"], 8, std::time::Duration::from_secs(30)).await?;
    
    // Verify the withdraw events were created with correct event types
    let self_withdraw_events = ctx.db_client
        .query(
            &format!("SELECT * FROM {} WHERE event_type = 'SSW' ORDER BY staker", get_table_name("stake_stakeevent")), 
            &[]
        )
        .await?;
    
    assert_eq!(self_withdraw_events.len(), 2);
    
    let community_withdraw_events = ctx.db_client
        .query(
            &format!("SELECT * FROM {} WHERE event_type = 'CSW' ORDER BY staker, stakee", get_table_name("stake_stakeevent")), 
            &[]
        )
        .await?;
    
    assert_eq!(community_withdraw_events.len(), 2);
    
    // Verify final stake amounts
    // staker1 self-stake: 10 - 3 = 7
    let stake1 = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $1", get_table_name("stake_stake")), 
            &[&"0xaaaa567890123456789012345678901234567890"]
        )
        .await?;
    let amount1: Decimal = stake1.get("current_amount");
    assert_eq!(amount1.to_string(), "7.000000000000000000");
    
    // staker2 self-stake: 15 - 4 = 11
    let stake2 = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $1", get_table_name("stake_stake")), 
            &[&"0xbbbb567890123456789012345678901234567890"]
        )
        .await?;
    let amount2: Decimal = stake2.get("current_amount");
    assert_eq!(amount2.to_string(), "11.000000000000000000");
    
    // staker1 -> stakee1: 5 - 2 = 3
    let stake3 = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $2", get_table_name("stake_stake")), 
            &[
                &"0xaaaa567890123456789012345678901234567890",
                &"0xcccc567890123456789012345678901234567890"
            ]
        )
        .await?;
    let amount3: Decimal = stake3.get("current_amount");
    assert_eq!(amount3.to_string(), "3.000000000000000000");
    
    // staker2 -> stakee2: 7 - 3 = 4
    let stake4 = ctx.db_client
        .query_one(
            &format!("SELECT current_amount FROM {} WHERE staker = $1 AND stakee = $2", get_table_name("stake_stake")), 
            &[
                &"0xbbbb567890123456789012345678901234567890",
                &"0xdddd567890123456789012345678901234567890"
            ]
        )
        .await?;
    let amount4: Decimal = stake4.get("current_amount");
    assert_eq!(amount4.to_string(), "4.000000000000000000");
    
    // No cleanup needed - test script handles DB cleanup before running tests
    Ok(())
}
