use chrono::prelude::{DateTime, Utc};
use ethers::types::H160;
use rust_decimal::prelude::*;
use rust_decimal::Decimal;

use crate::utils::{get_code_for_stake_event_type, StakeAmountOperation, StakeEventType};

#[derive(Debug, Clone, PartialEq)]
pub struct SqlCall {
    pub query: String,
    pub params: Vec<String>,
}

pub fn unix_time_to_datetime(unix_time: &u64) -> DateTime<Utc> {
    DateTime::from_timestamp(*unix_time as i64, 0).unwrap()
}

pub fn generate_add_or_extend_stake_sql(
    event_type: &StakeEventType,
    chain_id: u32,
    staker: &H160,
    stakee: &H160,
    increase_amount: &u128,
    unlock_time: &u64,
    block_timestamp: &u64,
    block_number: &u64,
    tx_hash: &str,
) -> Vec<SqlCall> {
    let chain_id: i32 = chain_id as i32;
    let staker = format!("{:#x}", staker);
    let stakee = format!("{:#x}", stakee);
    let mut increase_amount = Decimal::from_u128(*increase_amount).unwrap();
    increase_amount.set_scale(18).unwrap();
    let unlock_time = unix_time_to_datetime(unlock_time);
    let lock_time = unix_time_to_datetime(block_timestamp);
    let block_number = Decimal::from_u64(*block_number).unwrap();

    vec![
        SqlCall {
            query: "BEGIN".to_string(),
            params: vec![],
        },
        SqlCall {
            query: concat!(
                "INSERT INTO stake_stakeevent (event_type, chain, staker, stakee, amount, unlock_time, block_number, tx_hash)",
                " VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
            ).to_string(),
            params: vec![
                get_code_for_stake_event_type(event_type).to_string(),
                chain_id.to_string(),
                staker.clone(),
                stakee.clone(),
                increase_amount.to_string(),
                unlock_time.to_rfc3339(),
                block_number.to_string(),
                tx_hash.to_string(),
            ],
        },
        SqlCall {
            query: concat!(
                "INSERT INTO stake_stake as stake (chain, staker, stakee, unlock_time, lock_time, last_updated_in_block, current_amount)",
                " VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (chain, staker, stakee) DO UPDATE",
                " SET unlock_time = GREATEST(EXCLUDED.unlock_time, stake.unlock_time),",
                "     lock_time = GREATEST(EXCLUDED.lock_time, stake.lock_time),",
                "     last_updated_in_block = GREATEST(EXCLUDED.last_updated_in_block, stake.last_updated_in_block),",
                "     current_amount = stake.current_amount + EXCLUDED.current_amount",
            ).to_string(),
            params: vec![
                chain_id.to_string(),
                staker,
                stakee,
                unlock_time.to_rfc3339(),
                lock_time.to_rfc3339(),
                block_number.to_string(),
                increase_amount.to_string(),
            ],
        },
        SqlCall {
            query: "COMMIT".to_string(),
            params: vec![],
        },
    ]
}

pub fn generate_update_stake_amount_sql(
    event_type: &StakeEventType,
    chain_id: u32,
    staker: &H160,
    stakee: &H160,
    change_amount: &u128,
    operation: StakeAmountOperation,
    block_number: &u64,
    tx_hash: &str,
) -> Vec<SqlCall> {
    let chain_id: i32 = chain_id as i32;
    let staker = format!("{:#x}", staker);
    let stakee = format!("{:#x}", stakee);
    let mut change_amount = Decimal::from_u128(*change_amount).unwrap();
    change_amount.set_scale(18).unwrap();
    let amount = match operation {
        StakeAmountOperation::Add => change_amount,
        StakeAmountOperation::Subtract => -change_amount,
    };
    let block_number = Decimal::from_u64(*block_number).unwrap();

    vec![
        SqlCall {
            query: "BEGIN".to_string(),
            params: vec![],
        },
        SqlCall {
            query: concat!(
                "INSERT INTO stake_stakeevent (event_type, chain, staker, stakee, amount, block_number, tx_hash)",
                " VALUES ($1, $2, $3, $4, $5, $6, $7)"
            ).to_string(),
            params: vec![
                get_code_for_stake_event_type(event_type).to_string(),
                chain_id.to_string(),
                staker.clone(),
                stakee.clone(),
                amount.to_string(),
                block_number.to_string(),
                tx_hash.to_string(),
            ],
        },
        SqlCall {
            query: concat!(
                "UPDATE stake_stake as stake",
                " SET current_amount = current_amount + $1,",
                "     last_updated_in_block = GREATEST($5, stake.last_updated_in_block)",
                " WHERE chain = $2 AND staker = $3 AND stakee = $4",
            ).to_string(),
            params: vec![
                amount.to_string(),
                chain_id.to_string(),
                staker,
                stakee,
                block_number.to_string(),
            ],
        },
        SqlCall {
            query: "COMMIT".to_string(),
            params: vec![],
        },
    ]
}

pub fn generate_human_points_sql(
    address: &str,
    action: &str,
    timestamp: DateTime<Utc>,
    tx_hash: &str,
    chain_id: Option<u32>,
) -> Vec<SqlCall> {
    let address = address.to_lowercase();
    
    let mut sql_calls = vec![];
    
    if let Some(chain) = chain_id {
        sql_calls.push(SqlCall {
            query: "INSERT INTO registry_humanpoints (address, action, timestamp, tx_hash, chain_id) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING".to_string(),
            params: vec![
                address,
                action.to_string(),
                timestamp.to_rfc3339(),
                tx_hash.to_string(),
                (chain as i32).to_string(),
            ],
        });
    } else {
        sql_calls.push(SqlCall {
            query: "INSERT INTO registry_humanpoints (address, action, timestamp, tx_hash) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING".to_string(),
            params: vec![
                address,
                action.to_string(),
                timestamp.to_rfc3339(),
                tx_hash.to_string(),
            ],
        });
    }
    
    sql_calls
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::str::FromStr;

    #[test]
    fn test_self_stake_sql_generation() {
        let staker = H160::from_str("0xABCDEF1234567890123456789012345678901234").unwrap();
        let amount = 1_000_000_000_000_000_000u128; // 1 token with 18 decimals
        let unlock_time = 1700000000u64;
        let block_timestamp = 1699999999u64;
        let block_number = 12345u64;
        let tx_hash = "0xabc123";
        let chain_id = 1u32;

        let sql_calls = generate_add_or_extend_stake_sql(
            &StakeEventType::SelfStake,
            chain_id,
            &staker,
            &staker, // Self stake: staker == stakee
            &amount,
            &unlock_time,
            &block_timestamp,
            &block_number,
            &tx_hash,
        );

        // Should have 4 SQL calls: BEGIN, INSERT stake_stakeevent, INSERT/UPDATE stake_stake, COMMIT
        assert_eq!(sql_calls.len(), 4);
        
        // Check BEGIN
        assert_eq!(sql_calls[0].query, "BEGIN");
        assert_eq!(sql_calls[0].params.len(), 0);
        
        // Check stake_stakeevent INSERT
        let event_params = &sql_calls[1].params;
        assert_eq!(event_params[0], "SST"); // SelfStake code
        assert_eq!(event_params[1], "1"); // chain_id
        assert_eq!(event_params[2], "0xabcdef1234567890123456789012345678901234"); // lowercase staker
        assert_eq!(event_params[3], "0xabcdef1234567890123456789012345678901234"); // lowercase stakee (same as staker)
        assert_eq!(event_params[4], "1.000000000000000000"); // amount with 18 decimals
        assert_eq!(event_params[6], "12345"); // block_number
        assert_eq!(event_params[7], "0xabc123"); // tx_hash
        
        // Check stake_stake INSERT/UPDATE
        let stake_params = &sql_calls[2].params;
        assert_eq!(stake_params[0], "1"); // chain_id
        assert_eq!(stake_params[1], "0xabcdef1234567890123456789012345678901234"); // lowercase staker
        assert_eq!(stake_params[2], "0xabcdef1234567890123456789012345678901234"); // lowercase stakee
        assert_eq!(stake_params[5], "12345"); // block_number
        assert_eq!(stake_params[6], "1.000000000000000000"); // amount
        
        // Check COMMIT
        assert_eq!(sql_calls[3].query, "COMMIT");
        assert_eq!(sql_calls[3].params.len(), 0);
    }

    #[test]
    fn test_community_stake_sql_generation() {
        let staker = H160::from_str("0x1111111111111111111111111111111111111111").unwrap();
        let stakee = H160::from_str("0x2222222222222222222222222222222222222222").unwrap();
        let amount = 5_000_000_000_000_000_000u128; // 5 tokens
        let unlock_time = 1700000000u64;
        let block_timestamp = 1699999999u64;
        let block_number = 12345u64;
        let tx_hash = "0xdef456";
        let chain_id = 10u32; // Optimism

        let sql_calls = generate_add_or_extend_stake_sql(
            &StakeEventType::CommunityStake,
            chain_id,
            &staker,
            &stakee,
            &amount,
            &unlock_time,
            &block_timestamp,
            &block_number,
            &tx_hash,
        );

        let event_params = &sql_calls[1].params;
        assert_eq!(event_params[0], "CST"); // CommunityStake code
        assert_eq!(event_params[1], "10"); // chain_id
        assert_eq!(event_params[2], "0x1111111111111111111111111111111111111111"); // lowercase staker
        assert_eq!(event_params[3], "0x2222222222222222222222222222222222222222"); // lowercase stakee (different)
        assert_eq!(event_params[4], "5.000000000000000000"); // amount
    }

    #[test]
    fn test_slash_event_sql_generation() {
        let staker = H160::from_str("0x3333333333333333333333333333333333333333").unwrap();
        let stakee = H160::from_str("0x4444444444444444444444444444444444444444").unwrap();
        let amount = 100_000_000_000_000_000u128; // 0.1 tokens
        let block_number = 67890u64;
        let tx_hash = "0xslash123";
        let chain_id = 137u32; // Polygon

        let sql_calls = generate_update_stake_amount_sql(
            &StakeEventType::Slash,
            chain_id,
            &staker,
            &stakee,
            &amount,
            StakeAmountOperation::Subtract, // Slash is a subtraction
            &block_number,
            &tx_hash,
        );

        let event_params = &sql_calls[1].params;
        assert_eq!(event_params[0], "SLA"); // Slash code
        assert_eq!(event_params[4], "-0.100000000000000000"); // negative amount for slash
        
        let update_params = &sql_calls[2].params;
        assert_eq!(update_params[0], "-0.100000000000000000"); // negative amount in UPDATE
    }

    #[test]
    fn test_release_event_sql_generation() {
        let staker = H160::from_str("0x5555555555555555555555555555555555555555").unwrap();
        let stakee = staker;
        let amount = 2_500_000_000_000_000_000u128; // 2.5 tokens
        let block_number = 99999u64;
        let tx_hash = "0xrelease789";
        let chain_id = 42161u32; // Arbitrum

        let sql_calls = generate_update_stake_amount_sql(
            &StakeEventType::Release,
            chain_id,
            &staker,
            &stakee,
            &amount,
            StakeAmountOperation::Add, // Release is an addition
            &block_number,
            &tx_hash,
        );

        let event_params = &sql_calls[1].params;
        assert_eq!(event_params[0], "REL"); // Release code
        assert_eq!(event_params[4], "2.500000000000000000"); // positive amount for release
    }

    #[test]
    fn test_self_stake_withdrawn_sql_generation() {
        let staker = H160::from_str("0x6666666666666666666666666666666666666666").unwrap();
        let amount = 750_000_000_000_000_000u128; // 0.75 tokens
        let block_number = 11111u64;
        let tx_hash = "0xwithdraw111";
        let chain_id = 1u32;

        let sql_calls = generate_update_stake_amount_sql(
            &StakeEventType::SelfStakeWithdraw,
            chain_id,
            &staker,
            &staker, // Self stake withdrawn: staker == stakee
            &amount,
            StakeAmountOperation::Subtract,
            &block_number,
            &tx_hash,
        );

        let event_params = &sql_calls[1].params;
        assert_eq!(event_params[0], "SSW"); // SelfStakeWithdraw code
        assert_eq!(event_params[2], "0x6666666666666666666666666666666666666666"); // staker
        assert_eq!(event_params[3], "0x6666666666666666666666666666666666666666"); // stakee (same)
        assert_eq!(event_params[4], "-0.750000000000000000"); // negative amount
    }

    #[test]
    fn test_human_points_passport_mint_sql_generation() {
        let address = "0xABCDEF1234567890123456789012345678901234";
        let action = "PMT"; // Passport mint
        let timestamp = DateTime::from_timestamp(1700000000, 0).unwrap();
        let tx_hash = "0xpassport123";
        let chain_id = Some(10u32); // Optimism

        let sql_calls = generate_human_points_sql(
            address,
            action,
            timestamp,
            &tx_hash,
            chain_id,
        );

        assert_eq!(sql_calls.len(), 1);
        
        let params = &sql_calls[0].params;
        assert_eq!(params[0], "0xabcdef1234567890123456789012345678901234"); // lowercase address
        assert_eq!(params[1], "PMT");
        assert_eq!(params[3], "0xpassport123");
        assert_eq!(params[4], "10"); // chain_id
        
        // Check that ON CONFLICT DO NOTHING is included
        assert!(sql_calls[0].query.contains("ON CONFLICT DO NOTHING"));
    }

    #[test]
    fn test_human_points_holonym_mint_sql_generation() {
        let address = "0x7777777777777777777777777777777777777777";
        let action = "HIM"; // Holonym ID mint
        let timestamp = DateTime::from_timestamp(1700000000, 0).unwrap();
        let tx_hash = "0xholonym456";
        let chain_id = Some(10u32); // Optimism only

        let sql_calls = generate_human_points_sql(
            address,
            action,
            timestamp,
            &tx_hash,
            chain_id,
        );

        assert_eq!(sql_calls.len(), 1);
        
        let params = &sql_calls[0].params;
        assert_eq!(params[0], "0x7777777777777777777777777777777777777777"); // lowercase
        assert_eq!(params[1], "HIM");
        assert_eq!(params[4], "10"); // Optimism chain_id
    }

    #[test]
    fn test_decimal_precision() {
        // Test various amounts to ensure proper decimal handling
        let test_cases = vec![
            (1u128, "0.000000000000000001"), // 1 wei
            (1_000_000_000u128, "0.000000001000000000"), // 1 gwei
            (1_000_000_000_000_000_000u128, "1.000000000000000000"), // 1 token
            (123_456_789_012_345_678_901u128, "123.456789012345678901"), // large amount
        ];

        for (amount, expected) in test_cases {
            let mut decimal = Decimal::from_u128(amount).unwrap();
            decimal.set_scale(18).unwrap();
            assert_eq!(decimal.to_string(), expected);
        }
    }
    
    #[test]
    fn test_edge_case_zero_amount() {
        let staker = H160::from_str("0x0000000000000000000000000000000000000000").unwrap();
        let amount = 0u128; // Zero amount
        let unlock_time = 1700000000u64;
        let block_timestamp = 1699999999u64;
        let block_number = 12345u64;
        let tx_hash = "0xzero123";
        let chain_id = 1u32;

        let sql_calls = generate_add_or_extend_stake_sql(
            &StakeEventType::SelfStake,
            chain_id,
            &staker,
            &staker,
            &amount,
            &unlock_time,
            &block_timestamp,
            &block_number,
            &tx_hash,
        );

        let event_params = &sql_calls[1].params;
        assert_eq!(event_params[4], "0.000000000000000000"); // Zero amount with 18 decimals
    }
    
    #[test]
    fn test_community_stake_withdrawn_event() {
        let staker = H160::from_str("0x8888888888888888888888888888888888888888").unwrap();
        let stakee = H160::from_str("0x9999999999999999999999999999999999999999").unwrap();
        let amount = 333_333_333_333_333_333u128; // 0.333... tokens
        let block_number = 22222u64;
        let tx_hash = "0xcommunitywithdraw";
        let chain_id = 42161u32; // Arbitrum

        let sql_calls = generate_update_stake_amount_sql(
            &StakeEventType::CommunityStakeWithdraw,
            chain_id,
            &staker,
            &stakee,
            &amount,
            StakeAmountOperation::Subtract,
            &block_number,
            &tx_hash,
        );

        let event_params = &sql_calls[1].params;
        assert_eq!(event_params[0], "CSW"); // CommunityStakeWithdraw code
        assert_eq!(event_params[2], "0x8888888888888888888888888888888888888888");
        assert_eq!(event_params[3], "0x9999999999999999999999999999999999999999");
        assert_eq!(event_params[4], "-0.333333333333333333"); // negative amount
    }
    
    #[test]
    fn test_human_points_address_lowercase() {
        // Test that addresses are always lowercased
        let test_cases = vec![
            "0xABCDEF1234567890123456789012345678901234",
            "0xabcdef1234567890123456789012345678901234",
            "0xAbCdEf1234567890123456789012345678901234",
            "0xABCDEF1234567890123456789012345678901234",
        ];
        
        for address in test_cases {
            let sql_calls = generate_human_points_sql(
                address,
                "PMT",
                DateTime::from_timestamp(1700000000, 0).unwrap(),
                "0xtest",
                Some(10),
            );
            
            // All addresses should be lowercased
            assert_eq!(sql_calls[0].params[0], "0xabcdef1234567890123456789012345678901234");
        }
    }
    
    #[test]
    fn test_human_points_without_chain_id() {
        let address = "0xDEADBEEF00000000000000000000000000000000";
        let action = "PMT";
        let timestamp = DateTime::from_timestamp(1700000000, 0).unwrap();
        let tx_hash = "0xnochain";

        let sql_calls = generate_human_points_sql(
            address,
            action,
            timestamp,
            &tx_hash,
            None, // No chain ID
        );

        assert_eq!(sql_calls.len(), 1);
        // Should only have 4 params when no chain_id
        assert_eq!(sql_calls[0].params.len(), 4);
        assert_eq!(sql_calls[0].params[0], "0xdeadbeef00000000000000000000000000000000");
        assert_eq!(sql_calls[0].params[1], "PMT");
        assert_eq!(sql_calls[0].params[3], "0xnochain");
        
        // Query should not include chain_id column
        assert!(!sql_calls[0].query.contains("chain_id"));
    }
    
    #[test]
    fn test_large_block_numbers() {
        let staker = H160::from_str("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF").unwrap();
        let amount = 1_000_000_000_000_000_000u128;
        let block_number = u64::MAX; // Maximum u64 value
        let tx_hash = "0xmaxblock";
        let chain_id = 1u32;

        let sql_calls = generate_update_stake_amount_sql(
            &StakeEventType::Release,
            chain_id,
            &staker,
            &staker,
            &amount,
            StakeAmountOperation::Add,
            &block_number,
            &tx_hash,
        );

        let event_params = &sql_calls[1].params;
        assert_eq!(event_params[5], "18446744073709551615"); // block_number is param 5
        assert_eq!(event_params[6], "0xmaxblock"); // tx_hash is param 6
        
        let update_params = &sql_calls[2].params;
        assert_eq!(update_params[4], "18446744073709551615"); // block_number in UPDATE
    }
}