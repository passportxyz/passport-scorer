use std::str::FromStr;

use rust_decimal::prelude::*;
use tokio;
use tokio_postgres::{Client, Error, NoTls};

use crate::CONTRACT_START_BLOCK;

pub struct PostgresClient {
    client: Client,
}

impl PostgresClient {
    pub async fn new(database_url: &str) -> Result<Self, Error> {
        let (client, connection) = tokio_postgres::connect(database_url, NoTls).await?;
        tokio::spawn(async move {
            if let Err(e) = connection.await {
                eprintln!("Error - Failed to establish postgres connection: {}", e);
            }
        });
        Ok(Self { client })
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
        self.client.execute("INSERT INTO registry_gtcstakeevent (event_type, round_id, staker, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7)",&[&"SelfStake", &round_id, &staker, &decimal_amount, &staked, &block_number, &tx_hash]).await?;
        println!("Row inserted into registry_gtcstakeevent with type SelfStake!");
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
        self.client.execute("INSERT INTO registry_gtcstakeevent (event_type, round_id, staker, address, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)", &[&"Xstake", &round_id, &staker, &user, &decimal_amount, &staked, &block_number, &tx_hash]).await?;
        println!("Row inserted into registry_gtcstakeevent with type Xstake!");
        Ok(())
    }
    pub async fn get_latest_block(&self) -> Result<i32, Error> {
        let latest_block_rows = self
            .client
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
