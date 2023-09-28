use tokio;
use tokio_postgres::{Client, Error, NoTls};

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
                  staked BOOLEAN NOT NULL
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
    ) -> Result<(), Error> {
        self.client.execute(
      "INSERT INTO GTCStakeEvents (event_type, round_id, staker, amount, staked) VALUES ($1, $2, $3, $4, $5)",
      &[&"SelfStake", &round_id, &staker, &amount, &staked],
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
    ) -> Result<(), Error> {
        self.client.execute(
      "INSERT INTO GTCStakeEvents (event_type, round_id, staker, address, amount, staked) VALUES ($1, $2, $3, $4, $5, $6)",
      &[&"Xstake", &round_id, &staker, &user, &amount, &staked],
  ).await?;

        println!("Row inserted into GTCStakeEvents with type Xstake!");
        Ok(())
    }
}
