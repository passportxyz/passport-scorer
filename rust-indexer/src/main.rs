use dotenv::dotenv;
use ethers::{
    contract::abigen,
    core::types::{Address, Filter, H160, H256, U256},
    providers::{Http, Middleware, Provider, StreamExt, Ws},
};
use eyre::Result;
use std::{env, str::FromStr, sync::Arc};

abigen!(
    IDStaking,
    r#"[
        event selfStake(uint256 roundId,address staker,uint256 amount,bool staked)
        event xStake(uint256 roundId,address staker,address user,uint256 amount,bool staked)
    ]"#,
);

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    let get_env = |var| {
        env::var(var).map_err(|_| panic!("Required environment variable \"{}\" not set", var))
    };

    let id_staking_address = "0x0E3efD5BE54CC0f4C64e0D186b0af4b7F2A0e95F".parse::<Address>()?;

    let rpc_url = get_env("RPC_URL").unwrap();

    let provider = Provider::<Ws>::connect(rpc_url).await?;
    let client = Arc::new(provider);

    let current_block = client.get_block_number().await?;
    // block contract was deployed at
    let contract_start_block = 16401336;

    let id_staking = IDStaking::new(id_staking_address, client.clone());

    let mut last_queried_block = current_block;

    // You can make eth_getLogs requests with up to a 2K block range and no limit on the response size
    while last_queried_block > current_block {
        let next_block_range = last_queried_block + 2000;
        let previous_events = id_staking
            .events()
            .from_block(last_queried_block)
            .to_block(next_block_range)
            .query()
            .await?;

        for event in previous_events.iter() {
            // match log.topics[
            dbg!(event);
        }

        last_queried_block = next_block_range;
    }

    let future_events = id_staking.events().from_block(current_block);

    let mut stream = future_events.stream().await?.with_meta();

    // https://www.gakonst.com/ethers-rs/contracts/events-with-meta.html
    while let Some(Ok((event, meta))) = stream.next().await {
        dbg!(event);
        dbg!(meta);
    }

    Ok(())
}
