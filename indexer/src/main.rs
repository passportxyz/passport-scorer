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

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    let rpc_url = get_env("RPC_URL");

    let client = Provider::<Ws>::connect(&rpc_url).await?;

    let postgres_client = PostgresClient::new().await?;

    let mut block_indexer = StakingIndexer::new(Arc::new(client.clone()), postgres_client.clone());

    let mut staking_indexer =
        StakingIndexer::new(Arc::new(client.clone()), postgres_client.clone());

    let _result = try_join!(
        block_indexer.listen_for_blocks(),
        staking_indexer.listen_for_stake_events()
    )?;

    Ok(())
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

    pub async fn listen_for_blocks(&mut self) -> Result<()> {
        match self.client.subscribe_blocks().await {
            Ok(mut stream) => loop {
                let block = stream.next().await;
                match block {
                    Some(block) => {
                        println!(
                            "New Block - timestamp: {:?}, number: {}, hash: {:?}",
                            block.timestamp,
                            block.number.unwrap(),
                            block.hash.unwrap()
                        );
                    }
                    None => {
                        eprintln!("Error - Failed to get block");
                        panic!("Failed to get block");
                    }
                }
            },
            Err(err) => {
                eprintln!("Error - Failed to subscribe to blocks: {}", err);
                panic!("Failed to subscribe to blocks");
            }
        }
    }

    async fn listen_for_stake_events(&mut self) -> Result<()> {
        let current_block = self.client.get_block_number().await?;

        // This is the block number from which we want to start querying events. Either the contract initiation or the last block we queried.
        let query_start_block = &self.postgres_client.get_latest_block().await?;

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

        let future_events = self.id_staking_contract.events().from_block(current_block);

        let mut stream = future_events.stream().await?.with_meta();

        while let Some(event) = stream.next().await {
            match event {
                Ok((event_value, meta)) => {
                    match event_value {
                        IDStakingEvents::SelfStakeFilter(event_value) => {
                            let block_number = meta.block_number.as_u32();
                            let tx_hash = format!("{:?}", meta.transaction_hash);

                            self.format_and_save_self_stake_event(
                                &event_value,
                                block_number,
                                tx_hash,
                            )
                            .await?;
                        }
                        IDStakingEvents::XstakeFilter(event_value) => {
                            let block_number = meta.block_number.as_u32();
                            let tx_hash = format!("{:?}", meta.transaction_hash);
                            self.format_and_save_x_stake_event(&event_value, block_number, tx_hash)
                                .await?
                        }
                        _ => {
                            // Catch all for unhandled events
                        }
                    }
                }
                Err(err) => {
                    eprintln!("Error - Failed to IDStaking events: {}", err);
                    panic!("Failed to stream event")
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
