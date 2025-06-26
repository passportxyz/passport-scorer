extern crate chrono;

use chrono::prelude::{DateTime, Utc};
use deadpool_postgres::{Manager, ManagerConfig, Pool, RecyclingMethod};
use ethers::types::H160;
use rust_decimal::prelude::*;
use rust_decimal::Decimal;
use rustls::ClientConfig as RustlsClientConfig;
use std::str::FromStr;
use std::{fs::File, io::BufReader};
use tokio_postgres::{Error, NoTls};
use tokio_postgres_rustls::MakeRustlsConnect;

use crate::{
    utils::{get_code_for_stake_event_type, get_env, StakeAmountOperation, StakeEventType},
    LEGACY_CONTRACT_START_BLOCK,
};

fn get_table_name(base_name: &str) -> String {
    if let Ok(suffix) = std::env::var("TEST_TABLE_SUFFIX") {
        format!("{}{}", base_name, suffix)
    } else {
        base_name.to_string()
    }
}

#[derive(Debug, Clone)]
pub struct PostgresClient {
    pub pool: Pool,
}

impl PostgresClient {
    pub async fn new() -> Result<Self, Error> {
        let mut pg_config = tokio_postgres::Config::new();

        pg_config
            .user(&get_env("DB_USER"))
            .password(get_env("DB_PASSWORD"))
            .dbname(&get_env("DB_NAME"))
            .host(&get_env("DB_HOST"))
            .port(get_env("DB_PORT").parse::<u16>().unwrap());

        let ca_cert = get_env("CERT_FILE");

        let mgr_config = ManagerConfig {
            recycling_method: RecyclingMethod::Fast,
        };

        println!("cert_file: {}", ca_cert);
        let mgr: Option<Manager>;

        if ca_cert != "" {
            println!("Using TLS");

            let cert_file = File::open(ca_cert).unwrap();

            let mut buf = BufReader::new(cert_file);
            let mut root_store: rustls::RootCertStore = rustls::RootCertStore::empty();
            for cert in rustls_pemfile::certs(&mut buf) {
                root_store.add(cert.unwrap()).unwrap();
            }

            let tls_config = RustlsClientConfig::builder()
                .with_root_certificates(root_store)
                .with_no_client_auth();

            let tls = MakeRustlsConnect::new(tls_config);

            mgr = Some(Manager::from_config(pg_config, tls, mgr_config));
        } else {
            println!("Using NoTls");
            mgr = Some(Manager::from_config(pg_config, NoTls, mgr_config));
        }

        let pool = Pool::builder(mgr.unwrap()).max_size(16).build().unwrap();

        let ret = Self { pool };

        Ok(ret)
    }

    // This function is for legacy staking contract events
    pub async fn insert_into_combined_stake_filter_self_stake_legacy(
        &self,
        round_id: i32,
        staker: &str,
        amount: &str,
        staked: bool,
        block_number: i32,
        tx_hash: &str,
    ) -> Result<(), Error> {
        let mut decimal_amount = Decimal::from_str(amount).unwrap();
        let _ = decimal_amount.set_scale(18).unwrap();
        let client = self.pool.get().await.unwrap();
        client.execute(&format!("INSERT INTO {} (event_type, round_id, staker, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7)", get_table_name("registry_gtcstakeevent")),&[&"SelfStake", &round_id, &staker, &decimal_amount, &staked, &block_number, &tx_hash]).await?;
        println!(
            "Row inserted into {} with type SelfStake for block {} for legacy contract!", get_table_name("registry_gtcstakeevent"),
            block_number
        );
        Ok(())
    }

    // This function is for legacy staking contract events
    pub async fn insert_into_combined_stake_filter_xstake_legacy(
        &self,
        round_id: i32,
        staker: &str,
        user: &str,
        amount: &str,
        staked: bool,
        block_number: i32,
        tx_hash: &str,
    ) -> Result<(), Error> {
        let mut decimal_amount = Decimal::from_str(amount).unwrap();
        let _ = decimal_amount.set_scale(18).unwrap();
        let client = self.pool.get().await.unwrap();
        client.execute(&format!("INSERT INTO {} (event_type, round_id, staker, address, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)", get_table_name("registry_gtcstakeevent")), &[&"Xstake", &round_id, &staker, &user, &decimal_amount, &staked, &block_number, &tx_hash]).await?;
        println!(
            "Row inserted into {} with type Xstake for block {} for legacy contract!", get_table_name("registry_gtcstakeevent"),
            block_number
        );
        Ok(())
    }

    fn unix_time_to_datetime(&self, unix_time: &u64) -> DateTime<Utc> {
        DateTime::from_timestamp(*unix_time as i64, 0).unwrap()
    }

    pub async fn add_or_extend_stake(
        &self,
        event_type: &StakeEventType,
        chain_id: u32,
        staker: &H160,
        stakee: &H160,
        increase_amount: &u128,
        unlock_time: &u64,
        block_timestamp: &u64,
        block_number: &u64,
        tx_hash: &str,
    ) -> Result<(), Error> {
        let chain_id: i32 = chain_id as i32;
        let staker = format!("{:#x}", staker);
        let stakee = format!("{:#x}", stakee);
        let mut increase_amount = Decimal::from_u128(*increase_amount).unwrap();
        increase_amount.set_scale(18).unwrap();
        let unlock_time = self.unix_time_to_datetime(unlock_time);
        let lock_time = self.unix_time_to_datetime(block_timestamp);
        let block_number = Decimal::from_u64(*block_number).unwrap();

        let client = self.pool.get().await.unwrap();

        // begin transaction
        client.execute("BEGIN", &[]).await?;

        let do_query = async {
            // Log raw event
            client.execute(
                &format!(
                    "INSERT INTO {} (event_type, chain, staker, stakee, amount, unlock_time, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                    get_table_name("stake_stakeevent")
                ),
                &[&get_code_for_stake_event_type(event_type), &chain_id, &staker, &stakee, &increase_amount, &unlock_time, &block_number, &tx_hash]
            ).await?;

            // Log current stake state
            client.execute(
                &format!(
                    "INSERT INTO {} as stake (chain, staker, stakee, unlock_time, lock_time, last_updated_in_block, current_amount) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (chain, staker, stakee) DO UPDATE SET unlock_time = GREATEST(EXCLUDED.unlock_time, stake.unlock_time), lock_time = GREATEST(EXCLUDED.lock_time, stake.lock_time), last_updated_in_block = GREATEST(EXCLUDED.last_updated_in_block, stake.last_updated_in_block), current_amount = stake.current_amount + EXCLUDED.current_amount",
                    get_table_name("stake_stake")
                ),
                &[&chain_id, &staker, &stakee, &unlock_time, &lock_time, &block_number, &increase_amount]
            ).await?;

            Ok::<(), Error>(())
        };

        match do_query.await {
            Ok(_) => {
                // commit transaction
                client.execute("COMMIT", &[]).await?;
            }
            Err(e) => {
                // rollback transaction
                client.execute("ROLLBACK", &[]).await?;
                // continue if duplicate key error
                if format!("{:?}", e).contains(&format!(
                    "Key (tx_hash, chain, stakee)=({}, {}, {}) already exists.",
                    tx_hash, chain_id, stakee
                )) {
                    return Ok(());
                }
                return Err(e);
            }
        }

        println!(
            "Added or extended stake in block {} on chain {}!",
            block_number, chain_id
        );

        Ok(())
    }

    pub async fn update_stake_amount(
        &self,
        event_type: &StakeEventType,
        chain_id: u32,
        staker: &H160,
        stakee: &H160,
        change_amount: &u128,
        operation: StakeAmountOperation,
        block_number: &u64,
        tx_hash: &str,
    ) -> Result<(), Error> {
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

        let client = self.pool.get().await.unwrap();

        // begin transaction
        client.execute("BEGIN", &[]).await?;

        let do_query = async {
            // Log raw event
            client.execute(
                    &format!(
                        "INSERT INTO {} (event_type, chain, staker, stakee, amount, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                        get_table_name("stake_stakeevent")
                    ),
                    &[&get_code_for_stake_event_type(event_type), &chain_id, &staker, &stakee, &amount, &block_number, &tx_hash],
                )
                .await?;

            // Log current stake state
            client
                .execute(
                    &format!(
                        "UPDATE {} as stake SET current_amount = current_amount + $1, last_updated_in_block = GREATEST($5, stake.last_updated_in_block) WHERE chain = $2 AND staker = $3 AND stakee = $4",
                        get_table_name("stake_stake")
                    ),
                    &[&amount, &chain_id, &staker, &stakee, &block_number],
                )
                .await?;

            Ok::<(), Error>(())
        };

        match do_query.await {
            Ok(_) => {
                // commit transaction
                client.execute("COMMIT", &[]).await?;
            }
            Err(e) => {
                // rollback transaction
                client.execute("ROLLBACK", &[]).await?;
                // continue if duplicate key error
                if format!("{:?}", e).contains(&format!(
                    "Key (tx_hash, chain, stakee)=({}, {}, {}) already exists.",
                    tx_hash, chain_id, stakee
                )) {
                    return Ok(());
                }
                return Err(e);
            }
        }

        println!(
            "Modified stake amount in block {} on chain {}!",
            block_number, chain_id
        );

        Ok(())
    }

    pub async fn get_requested_start_block(&self, chain_id: u32) -> Result<u64, Error> {
        let chain_id: i32 = chain_id as i32;
        let client = self.pool.get().await.unwrap();
        let start_block_rows = client
            .query(
                &format!("SELECT start_block_number FROM {} WHERE chain = $1 AND pending = true", get_table_name("stake_reindexrequest")),
                &[&chain_id],
            )
            .await?;

        match start_block_rows.get(0) {
            Some(row) => {
                let start_block: Decimal = row.get("start_block_number");
                Ok(start_block.to_u64().unwrap())
            }
            None => Ok(0),
        }
    }

    pub async fn acknowledge_requested_start_block(&self, chain_id: u32) -> Result<(), Error> {
        let chain_id: i32 = chain_id as i32;
        let client = self.pool.get().await.unwrap();
        client
            .execute(
                &format!("UPDATE {} SET pending = false WHERE chain = $1 and pending = true", get_table_name("stake_reindexrequest")),
                &[&chain_id],
            )
            .await?;
        Ok(())
    }

    pub async fn get_total_event_count(&self, chain_id: u32) -> Result<i64, Error> {
        let chain_id: i32 = chain_id as i32;
        let client = self.pool.get().await.unwrap();

        // Count stake events
        let stake_count_rows = client
            .query(
                &format!("SELECT COUNT(*) FROM {} WHERE chain = $1", get_table_name("stake_stakeevent")),
                &[&chain_id],
            )
            .await?;

        let stake_count: i64 = stake_count_rows
            .get(0)
            .map(|row| row.get("count"))
            .unwrap_or(0);

        // Count human points events for this chain (only PMT and HIM actions)
        let human_points_count_rows = client
            .query(
                &format!("SELECT COUNT(*) FROM {} WHERE chain_id = $1 AND action IN ('PMT', 'HIM')", get_table_name("registry_humanpoints")),
                &[&chain_id],
            )
            .await?;

        let human_points_count: i64 = human_points_count_rows
            .get(0)
            .map(|row| row.get("count"))
            .unwrap_or(0);

        Ok(stake_count + human_points_count)
    }

    pub async fn get_latest_block(&self, chain_id: u32) -> Result<u64, Error> {
        let chain_id: i32 = chain_id as i32;
        let client = self.pool.get().await.unwrap();
        let latest_block_rows = client
            .query(
                &format!("SELECT block_number FROM {} WHERE chain = $1 LIMIT 1;", get_table_name("stake_lastblock")),
                &[&chain_id],
            )
            .await?;

        match latest_block_rows.get(0) {
            Some(row) => {
                let latest_block: Decimal = row.get("block_number");
                Ok(latest_block.to_u64().unwrap())
            }
            None => Ok(0),
        }
    }

    pub async fn get_latest_block_legacy(&self) -> Result<i32, Error> {
        let block = self.get_latest_block(0).await?;
        if block == 0 {
            return Ok(LEGACY_CONTRACT_START_BLOCK);
        }
        Ok(block as i32)
    }

    pub async fn update_last_checked_block(
        &self,
        chain_id: u32,
        block_number: &u64,
    ) -> Result<(), Error> {
        let chain_id: i32 = chain_id as i32;
        let block_number = Decimal::from_u64(*block_number).unwrap();

        let client = self.pool.get().await.unwrap();

        client
            .execute(
                &format!(
                    "UPDATE {} SET block_number = $2 WHERE chain = $1 AND block_number < $2",
                    get_table_name("stake_lastblock")
                ),
                &[&chain_id, &block_number],
            )
            .await?;

        Ok(())
    }

    pub async fn update_last_checked_block_legacy(&self, block_number: u32) -> Result<(), Error> {
        self.update_last_checked_block(0, &(block_number as u64))
            .await
    }

    pub async fn add_human_points_event(
        &self,
        address: &str,
        action: &str,
        timestamp: DateTime<Utc>,
        tx_hash: &str,
        chain_id: Option<u32>,
    ) -> Result<(), Error> {
        let address = address.to_lowercase();
        let client = self.pool.get().await.unwrap();

        match chain_id {
            Some(chain) => {
                let chain: i32 = chain as i32;
                client
                    .execute(
                        &format!("INSERT INTO {} (address, action, timestamp, tx_hash, chain_id) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING", get_table_name("registry_humanpoints")),
                        &[&address, &action, &timestamp, &tx_hash, &chain],
                    )
                    .await?;
            }
            None => {
                client
                    .execute(
                        &format!("INSERT INTO {} (address, action, timestamp, tx_hash) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING", get_table_name("registry_humanpoints")),
                        &[&address, &action, &timestamp, &tx_hash],
                    )
                    .await?;
            }
        }

        eprintln!(
            "Debug - Recorded {} action for {} in tx {}",
            action, address, tx_hash
        );

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal_macros::dec;

    #[test]
    fn test_decimal_precision_handling() {
        // Test that our decimal handling maintains precision
        let test_cases = vec![
            ("1", dec!(0.000000000000000001)),
            ("1000000000000000000", dec!(1.0)),
            ("1500000000000000000", dec!(1.5)),
            ("999999999999999999", dec!(0.999999999999999999)),
            ("1000000000000000001", dec!(1.000000000000000001)),
        ];
        
        for (wei_str, expected) in test_cases {
            let mut decimal = Decimal::from_str(wei_str).unwrap();
            decimal.set_scale(18).unwrap();
            assert_eq!(
                decimal, expected,
                "Wei string {} should convert to {}",
                wei_str, expected
            );
        }
    }

    #[test]
    fn test_address_lowercase_normalization() {
        // This mimics what happens in add_human_points_event
        let test_addresses = vec![
            ("0xABCDEF1234567890123456789012345678901234", "0xabcdef1234567890123456789012345678901234"),
            ("0xAbCdEf1234567890123456789012345678901234", "0xabcdef1234567890123456789012345678901234"),
            ("already_lowercase", "already_lowercase"),
        ];
        
        for (input, expected) in test_addresses {
            let normalized = input.to_lowercase();
            assert_eq!(normalized, expected);
        }
    }
}
