mod postgres;

use dotenv::dotenv;
use ethers::{
    contract::abigen,
    core::types::Address,
    providers::{Middleware, Provider, PubsubClient, StreamExt, Ws},
};
use eyre::Result;
use futures::try_join;
use postgres::PostgresClient;
use std::{env, sync::Arc};

abigen!(
    IDStaking,
    r#"[
        event selfStake(uint256 roundId,address staker,uint256 amount,bool staked)
        event xStake(uint256 roundId,address staker,address user,uint256 amount,bool staked)
        event tokenMigrated(address staker,uint256 amount,uint256 fromRound,uint256 toRound)
        event roundCreated(uint256 id)
        event RoleAdminChanged(bytes32 indexed role, bytes32 indexed previousAdminRole, bytes32 indexed newAdminRole)
        event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender)
        event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender)
    ]"#,
);

pub const CONTRACT_START_BLOCK: i32 = 16403024;

pub fn get_env(var: &str) -> String {
    env::var(var).unwrap_or_else(|_| panic!("Required environment variable \"{}\" not set", var))
}

pub async fn connect_with_reconnects(rpc_url: &String) -> Option<Provider<Ws>> {
    match Provider::<Ws>::connect_with_reconnects(rpc_url, 0).await {
        Ok(p) => Some(p),
        Err(e) => {
            eprintln!("Warning - Stream reconnect attempt failed: {e}");
            None
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    loop {
        let postgres_client = PostgresClient::new().await?;

        // This is the block number from which we want to start querying events. Either the contract initiation or the last block we queried.
        let query_start_block = postgres_client.get_latest_block().await?;

        match try_join!(
            throw_when_no_events_logged(&query_start_block, &postgres_client),
            run_listen_loop(&query_start_block, &postgres_client),
        ) {
            Ok(_) => {
                eprintln!("Warning - top-level join ended without error");
            }
            Err(err) => {
                if err.to_string().contains("No events logged in the last 15 minutes") {
                    eprintln!("Warning - resetting due to no events logged in the last 15 minutes");
                } else {
                    eprintln!("Warning - top-level join ended with error, {}", err);
                }
            }
        }
    }
}

async fn throw_when_no_events_logged(
    starting_event_block: &i32,
    postgres_client: &PostgresClient,
) -> Result<()> {
    let mut start_block = *starting_event_block;
    loop {
        // sleep for 15 minutes
        tokio::time::sleep(tokio::time::Duration::from_secs(900)).await;

        let latest_logged_block = postgres_client.get_latest_block().await?;

        if latest_logged_block == start_block {
            return Err(eyre::eyre!("No events logged in the last 15 minutes"));
        }

        start_block = latest_logged_block;
    }
}

async fn run_listen_loop(query_start_block: &i32, postgres_client: &PostgresClient) -> Result<()> {
    let rpc_url = get_env("RPC_URL");

    let mut num_retries = 0;
    let delay_base: u64 = 2;

    loop {
        let Some(client) = connect_with_reconnects(&rpc_url).await else {
            eprintln!(
                "Warning - Failed to connect to RPC, retry attempt #{}",
                num_retries
            );
            tokio::time::sleep(tokio::time::Duration::from_secs(
                delay_base.pow(num_retries),
            ))
            .await;
            if num_retries % 4 == 0 {
                eprintln!("Error - Failed repeatedly to connect to RPC");
            }
            num_retries += 1;
            continue;
        };
        num_retries = 0;

        let mut staking_indexer =
            StakingIndexer::new(Arc::new(client.clone()), postgres_client.clone());

        match staking_indexer
            .listen_for_stake_events(&query_start_block)
            .await
        {
            Ok(_) => {
                eprintln!("Warning - listen_for_stake_events ended without error");
            }
            Err(err) => {
                eprintln!("Error - Failed listen_for_stake_events with error {}", err);
            }
        }
    }
}

pub struct StakingIndexer<M: Middleware>
where
    M::Provider: PubsubClient,
{
    client: Arc<M>,
    id_staking_contract: IDStaking<M>,
    postgres_client: PostgresClient,
}

impl<M: Middleware + 'static> StakingIndexer<M>
where
    M::Provider: PubsubClient,
{
    pub fn new(client: Arc<M>, postgres_client: PostgresClient) -> Self {
        let id_staking_address = "0x0E3efD5BE54CC0f4C64e0D186b0af4b7F2A0e95F"
            .parse::<Address>()
            .unwrap();

        let id_staking_contract = IDStaking::new(id_staking_address, client.clone());

        Self {
            client,
            id_staking_contract,
            postgres_client,
        }
    }

    async fn listen_for_stake_events(&mut self, query_start_block: &i32) -> Result<()> {
        let current_block = self.client.get_block_number().await?;

        let mut last_queried_block: u32 = (*query_start_block)
            .try_into()
            .expect("Block number out of range");

        // Increment the last queried block by 1 to avoid querying the same block twice
        last_queried_block = last_queried_block + 1;

        // You can make eth_getLogs requests with up to a 2K block range and no limit on the response size
        while last_queried_block < current_block.as_u32() {
            let next_block_range = last_queried_block.clone() + 2000;
            let previous_events_query = self
                .id_staking_contract
                .events()
                .from_block(last_queried_block)
                .to_block(next_block_range)
                .query_with_meta()
                .await;

            match previous_events_query {
                Ok(previous_events) => {
                    for (event, meta) in previous_events.iter() {
                        match event {
                            IDStakingEvents::SelfStakeFilter(event) => {
                                let block_number = meta.block_number.as_u32();
                                let tx_hash = format!("{:?}", meta.transaction_hash);

                                self.format_and_save_self_stake_event(
                                    &event,
                                    block_number,
                                    tx_hash,
                                )
                                .await?;
                            }
                            IDStakingEvents::XstakeFilter(event) => {
                                let block_number = meta.block_number.as_u32();
                                let tx_hash = format!("{:?}", meta.transaction_hash);
                                self.format_and_save_x_stake_event(&event, block_number, tx_hash)
                                    .await?
                            }
                            _ => {
                                // Catch all for unhandled events
                            }
                        }
                    }
                }
                Err(err) => {
                    eprintln!(
                        "Error - Failed to query events: {}, {}, {}",
                        err, last_queried_block, next_block_range
                    );
                }
            }
            last_queried_block = next_block_range;
        }

        eprintln!("Debug - Finished querying past events");

        let future_events = self.id_staking_contract.events().from_block(current_block);

        let mut stream = future_events.stream().await?.with_meta();

        eprintln!("Debug - Listening for future events");

        while let Some(event) = stream.next().await {
            let (event_value, meta) = match event {
                Err(err) => {
                    eprintln!("Error - Failed to fetch IDStaking events: {}", err);
                    break;
                }
                Ok(event) => event,
            };

            let block_number = meta.block_number.as_u32();
            let tx_hash = format!("{:?}", meta.transaction_hash);

            match event_value {
                IDStakingEvents::SelfStakeFilter(event_value) => {
                    self.format_and_save_self_stake_event(&event_value, block_number, tx_hash)
                        .await?
                }
                IDStakingEvents::XstakeFilter(event_value) => {
                    self.format_and_save_x_stake_event(&event_value, block_number, tx_hash)
                        .await?
                }
                _ => {
                    eprintln!("Debug - Unhandled event in tx {}", tx_hash);
                }
            }
        }

        return Ok(());
    }

    pub async fn format_and_save_self_stake_event(
        &mut self,
        event: &SelfStakeFilter,
        block_number: u32,
        transaction_hash: String,
    ) -> Result<()> {
        let round_id = event.round_id.as_u32();

        // Convert H160 and U256 to String
        let staker_str = format!("{:?}", event.staker);

        let amount_str = format!("{}", event.amount);

        let staked = event.staked;
        if let Err(err) = self
            .postgres_client
            .insert_into_combined_stake_filter_self_stake(
                round_id.try_into().unwrap(),
                &staker_str,
                &amount_str,
                staked,
                block_number.try_into().unwrap(),
                &transaction_hash,
            )
            .await
        {
            eprintln!("Error - Failed to insert SelfStakeFilter: {}", err);
        }
        Ok(())
    }

    async fn format_and_save_x_stake_event(
        &mut self,
        event: &XstakeFilter,
        block_number: u32,
        transaction_hash: String,
    ) -> Result<()> {
        // Convert U256 to i32 for round_id
        // Be cautious about overflow, and implement a proper check if necessary
        let round_id_i32 = event.round_id.low_u32() as i32;

        // Convert H160 to String for staker and user
        let staker_str = format!("{:?}", event.staker);
        let user_str = format!("{:?}", event.user);
        // Convert U256 to String for amount
        let amount_str = format!("{}", event.amount);

        // Dereference the bool (if needed)
        let staked = event.staked;

        if let Err(err) = self
            .postgres_client
            .insert_into_combined_stake_filter_xstake(
                round_id_i32,
                &staker_str,
                &user_str,
                &amount_str,
                staked,
                block_number.try_into().unwrap(),
                &transaction_hash,
            )
            .await
        {
            eprintln!("Error - Failed to insert XstakeFilter: {}", err);
        }
        Ok(())
    }
}
