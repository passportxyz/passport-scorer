use std::str::FromStr;

use deadpool_postgres::{Manager, ManagerConfig, Pool, RecyclingMethod};
use rust_decimal::prelude::*;
use tokio_postgres::{Error, NoTls};

use crate::{get_env, CONTRACT_START_BLOCK};

#[derive(Debug, Clone)]
pub struct PostgresClient {
    pool: Pool,
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

        let mgr_config = ManagerConfig {
            recycling_method: RecyclingMethod::Fast,
        };
        let mgr = Manager::from_config(pg_config, NoTls, mgr_config);

        let pool = Pool::builder(mgr).max_size(16).build().unwrap();

        Ok(Self { pool })
    }

    pub async fn insert_into_combined_stake_filter_self_stake(
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
        client.execute("INSERT INTO registry_gtcstakeevent (event_type, round_id, staker, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7)",&[&"SelfStake", &round_id, &staker, &decimal_amount, &staked, &block_number, &tx_hash]).await?;
        println!(
            "Row inserted into registry_gtcstakeevent with type SelfStake for block {}!",
            block_number
        );
        Ok(())
    }

    pub async fn insert_into_combined_stake_filter_xstake(
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
        client.execute("INSERT INTO registry_gtcstakeevent (event_type, round_id, staker, address, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)", &[&"Xstake", &round_id, &staker, &user, &decimal_amount, &staked, &block_number, &tx_hash]).await?;
        println!(
            "Row inserted into registry_gtcstakeevent with type Xstake for block {}!",
            block_number
        );
        Ok(())
    }

    pub async fn get_latest_block(&self) -> Result<i32, Error> {
        let client = self.pool.get().await.unwrap();
        let latest_block_rows = client
            .query(
                "SELECT block_number FROM registry_gtcstakeevent ORDER BY id DESC LIMIT 1;",
                &[],
            )
            .await?;

        if let Some(row) = latest_block_rows.get(0) {
            // Extract and return the block number
            let latest_block: i32 = row.get("block_number");
            Ok(latest_block)
        } else {
            // return contract start block
            Ok(CONTRACT_START_BLOCK)
        }
    }
}
