mod legacy_staking_indexer;
mod postgres;
mod staking_indexer;
mod utils;

use std::collections::HashMap;
use dotenv::dotenv;
use ethers::core::types::Address;
use eyre::Result;
use futures::try_join;
use legacy_staking_indexer::LegacyStakingIndexer;
use postgres::PostgresClient;
use staking_indexer::StakingIndexer;
use utils::{get_env, Chain};

pub const LEGACY_CONTRACT_START_BLOCK: i32 = 16403024;
pub const LEGACY_CONTRACT_ADDRESS: &str = "0x0E3efD5BE54CC0f4C64e0D186b0af4b7F2A0e95F";

pub const CONTRACT_START_BLOCK_MAP: &[(Chain, u64)] =
    &[(Chain::Ethereum, 16403024), (Chain::Optimism, 0)];

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    loop {
        let postgres_client = initialize_postgres_client().await?;
        let contract_address = get_env("STAKING_CONTRACT_ADDRESS")
            .parse::<Address>()
            .unwrap();

        match try_join!(
            run_legacy_indexer(postgres_client.clone()),
            run_ethereum_indexer(postgres_client.clone(), &contract_address),
            run_optimism_indexer(postgres_client.clone(), &contract_address)
        ) {
            Ok(_) => {
                eprintln!("Warning - top-level join ended without error");
            }
            Err(err) => {
                eprintln!("Warning - top-level join ended with error, {}", err);
            }
        }
        // Loop facilitates starting over and recreating all connections if anything fails
        // (aka if the above try_join ever completes)
    }
}

async fn initialize_postgres_client() -> Result<PostgresClient> {
    let mut start_block_map = HashMap::new();
    start_block_map.insert(
        Chain::Ethereum,
        get_env("ETHEREUM_START_BLOCK").parse::<u64>().unwrap(),
    );
    start_block_map.insert(
        Chain::Optimism,
        get_env("OPTIMISM_START_BLOCK").parse::<u64>().unwrap(),
    );

    let postgres_client = PostgresClient::new(start_block_map).await?;
    Ok(postgres_client)
}

async fn run_legacy_indexer(postgres_client: PostgresClient) -> Result<()> {
    if get_env("ENABLE_LEGACY_STAKING_INDEXER") != "true" {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("ETHEREUM_RPC_URL");
    let legacy_staking_indexer = LegacyStakingIndexer::new(postgres_client, &ethereum_rpc_url);
    legacy_staking_indexer.listen_with_timeout_reset().await
}

async fn run_ethereum_indexer(postgres_client: PostgresClient, contract_address: &Address) -> Result<()> {
    if get_env("ENABLE_ETHEREUM_STAKING_INDEXER") != "true" {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("ETHEREUM_RPC_URL");
    let ethereum_staking_indexer =
        StakingIndexer::new(postgres_client, &ethereum_rpc_url, Chain::Ethereum, contract_address);
    ethereum_staking_indexer.listen_with_timeout_reset().await
}

async fn run_optimism_indexer(postgres_client: PostgresClient, contract_address: &Address) -> Result<()> {
    if get_env("ENABLE_OPTIMISM_STAKING_INDEXER") != "true" {
        return Ok(());
    }

    let optimism_rpc_url = get_env("OPTIMISM_RPC_URL");
    let optimism_staking_indexer =
        StakingIndexer::new(postgres_client, &optimism_rpc_url, Chain::Optimism, contract_address);
    optimism_staking_indexer.listen_with_timeout_reset().await
}
