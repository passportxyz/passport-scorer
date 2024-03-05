mod legacy_staking_indexer;
mod postgres;
mod staking_indexer;
mod utils;

use dotenv::dotenv;
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

pub const CONTRACT_ADDRESS: &str = "0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9";

pub const ENABLE_LEGACY_STAKING_INDEXER: bool = true;
pub const ENABLE_ETHEREUM_STAKING_INDEXER: bool = false;
pub const ENABLE_OPTIMISM_STAKING_INDEXER: bool = false;

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    loop {
        let postgres_client = PostgresClient::new().await?;

        match try_join!(
            run_legacy_indexer(postgres_client.clone()),
            run_ethereum_indexer(postgres_client.clone()),
            run_optimism_indexer(postgres_client.clone())
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

async fn run_legacy_indexer(postgres_client: PostgresClient) -> Result<()> {
    if !ENABLE_LEGACY_STAKING_INDEXER {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("ETHEREUM_RPC_URL");
    let legacy_staking_indexer = LegacyStakingIndexer::new(postgres_client, &ethereum_rpc_url);
    legacy_staking_indexer.listen_with_timeout_reset().await
}

async fn run_ethereum_indexer(postgres_client: PostgresClient) -> Result<()> {
    if !ENABLE_ETHEREUM_STAKING_INDEXER {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("ETHEREUM_RPC_URL");
    let ethereum_staking_indexer =
        StakingIndexer::new(postgres_client, &ethereum_rpc_url, Chain::Ethereum);
    ethereum_staking_indexer.listen_with_timeout_reset().await
}

async fn run_optimism_indexer(postgres_client: PostgresClient) -> Result<()> {
    if !ENABLE_OPTIMISM_STAKING_INDEXER {
        return Ok(());
    }

    let optimism_rpc_url = get_env("OPTIMISM_RPC_URL");
    let optimism_staking_indexer =
        StakingIndexer::new(postgres_client, &optimism_rpc_url, Chain::Optimism);
    optimism_staking_indexer.listen_with_timeout_reset().await
}
