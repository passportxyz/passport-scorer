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
                eprintln!("connection error: {}", e);
            }
        });
        dbg!("Connected to Postgres!");
        Ok(Self { client })
    }

    pub async fn create_table(&self) -> Result<(), Error> {
        self.client
            .execute(
                "CREATE TABLE IF NOT EXISTS GTCStakeEvents (
                  id SERIAL PRIMARY KEY,
                  event_type VARCHAR(15) NOT NULL,
                  round_id INT NOT NULL,
                  staker CHAR(42) NOT NULL,
                  address CHAR(42),
                  amount CHAR(42) NOT NULL,
                  staked BOOLEAN NOT NULL,
                  block_number INT NOT NULL,
                  tx_hash CHAR(66) NOT NULL
                );",
                &[],
            )
            .await?;

        println!("Table created!");
        Ok(())
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
        self.client.execute(
      "INSERT INTO GTCStakeEvents (event_type, round_id, staker, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7)",
      &[&"SelfStake", &round_id, &staker, &amount, &staked, &block_number, &tx_hash],
  ).await?;

        println!("Row inserted into GTCStakeEvents with type SelfStake!");
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
        self.client.execute(
      "INSERT INTO GTCStakeEvents (event_type, round_id, staker, address, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
      &[&"Xstake", &round_id, &staker, &user, &amount, &staked, &block_number, &tx_hash],
  ).await?;

        println!("Row inserted into GTCStakeEvents with type Xstake!");
        Ok(())
    }
    pub async fn get_latest_block(&self) -> Result<i32, Error> {
        let latest_block_rows = self
            .client
            .query(
                "SELECT block_number FROM GTCStakeEvents ORDER BY id DESC LIMIT 1;",
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
