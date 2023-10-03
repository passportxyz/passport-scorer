mod postgres;

use dotenv::dotenv;
use ethers::{
    contract::abigen,
    core::types::{Address, Filter, H160, H256, U256},
    providers::{Http, Middleware, Provider, StreamExt, Ws},
};
use eyre::Result;
use postgres::PostgresClient;
use std::{env, str::FromStr, sync::Arc};

abigen!(
    IDStaking,
    r#"[
        event selfStake(uint256 roundId,address staker,uint256 amount,bool staked)
        event xStake(uint256 roundId,address staker,address user,uint256 amount,bool staked)
    ]"#,
);

pub const CONTRACT_START_BLOCK: i32 = 16403024;

async fn format_and_save_self_stake_event(
    event: &SelfStakeFilter,
    block_number: u32,
    transaction_hash: String,
    postgres_client: &PostgresClient,
) -> Result<()> {
    let round_id = event.round_id.as_u32();

    // Convert H160 and U256 to String
    let staker_str = format!("{:?}", event.staker);
    let amount_str = format!("{}", event.amount);

    let staked = event.staked;
    if let Err(err) = postgres_client
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
        eprintln!("Failed to insert SelfStakeFilter: {}", err);
    }
    Ok(())
}

async fn format_and_save_x_stake_event(
    event: &XstakeFilter,
    block_number: u32,
    transaction_hash: String,
    postgres_client: &PostgresClient,
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

    if let Err(err) = postgres_client
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
        eprintln!("Failed to insert XstakeFilter: {}", err);
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    let get_env = |var| {
        env::var(var).map_err(|_| panic!("Required environment variable \"{}\" not set", var))
    };

    let id_staking_address = "0x0E3efD5BE54CC0f4C64e0D186b0af4b7F2A0e95F".parse::<Address>()?;

    let rpc_url = get_env("RPC_URL").unwrap();

    let database_url = get_env("DATABASE_URL").unwrap();

    let postgres_client = PostgresClient::new(&database_url).await?;
    postgres_client.create_table().await?;

    let provider = Provider::<Ws>::connect(rpc_url).await?;
    let client = Arc::new(provider);

    let current_block = client.get_block_number().await?;

    // This is the block number from which we want to start querying events. Either the contract initiation or the last block we queried.
    let query_start_block = postgres_client.get_latest_block().await?;

    let id_staking = IDStaking::new(id_staking_address, client.clone());

    let mut last_queried_block: u32 = query_start_block.try_into().unwrap();

    // You can make eth_getLogs requests with up to a 2K block range and no limit on the response size
    while last_queried_block < current_block.as_u32() {
        let next_block_range = last_queried_block.clone() + 2000;
        let previous_events_query = id_staking
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

                            format_and_save_self_stake_event(
                                &event,
                                block_number,
                                tx_hash,
                                &postgres_client,
                            )
                            .await?;
                        }
                        IDStakingEvents::XstakeFilter(event) => {
                            let block_number = meta.block_number.as_u32();
                            let tx_hash = format!("{:?}", meta.transaction_hash);
                            format_and_save_x_stake_event(
                                &event,
                                block_number,
                                tx_hash,
                                &postgres_client,
                            )
                            .await?
                        }
                    }
                }
            }
            Err(err) => {
                eprintln!("Failed to query events: {}", err); // Log the error
                                                              // You can also implement additional logic here, like retries or alerting.
            }
        }
        last_queried_block = next_block_range;
    }

    let future_events = id_staking.events().from_block(current_block);

    let mut stream = future_events.stream().await?.with_meta();

    while let Some(Ok((event, meta))) = stream.next().await {
        match event {
            IDStakingEvents::SelfStakeFilter(event) => {
                let block_number = meta.block_number.as_u32();
                let tx_hash = format!("{:?}", meta.transaction_hash);

                format_and_save_self_stake_event(&event, block_number, tx_hash, &postgres_client)
                    .await?;
            }
            IDStakingEvents::XstakeFilter(event) => {
                let block_number = meta.block_number.as_u32();
                let tx_hash = format!("{:?}", meta.transaction_hash);
                format_and_save_x_stake_event(&event, block_number, tx_hash, &postgres_client)
                    .await?
            }
        }
    }

    Ok(())
}
