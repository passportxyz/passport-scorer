mod chain_config;
mod legacy_staking_indexer;
mod postgres;
mod unified_indexer;
mod utils;

use dotenv::dotenv;
use ethers::core::types::Address;
use eyre::Result;
use futures::try_join;
use postgres::PostgresClient;
use std::sync::Arc;
use utils::get_env;

pub const LEGACY_CONTRACT_START_BLOCK: i32 = 16403024;
pub const LEGACY_CONTRACT_ADDRESS: &str = "0x0E3efD5BE54CC0f4C64e0D186b0af4b7F2A0e95F";

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    loop {
        let postgres_client = PostgresClient::new().await?;
        let contract_address_eth_mainnet = get_env("STAKING_CONTRACT_ADDRESS_ETH_MAINNET")
            .parse::<Address>()
            .unwrap();
        let contract_address_op_mainnet = get_env("STAKING_CONTRACT_ADDRESS_OP_MAINNET")
            .parse::<Address>()
            .unwrap();

        let contract_address_op_sepolia = get_env("STAKING_CONTRACT_ADDRESS_OP_SEPOLIA")
            .parse::<Address>()
            .unwrap();
        let contract_address_arbitrum_mainnet =
            get_env("STAKING_CONTRACT_ADDRESS_ARBITRUM_MAINNET")
                .parse::<Address>()
                .unwrap();

        let postgres_client = Arc::new(postgres_client);

        match try_join!(
            chain_config::create_legacy_indexer(postgres_client.clone()),
            chain_config::create_ethereum_indexer(
                postgres_client.clone(),
                &contract_address_eth_mainnet
            ),
            chain_config::create_optimism_indexer(
                postgres_client.clone(),
                &contract_address_op_mainnet
            ),
            chain_config::create_optimism_sepolia_indexer(
                postgres_client.clone(),
                &contract_address_op_sepolia
            ),
            chain_config::create_arbitrum_indexer(
                postgres_client.clone(),
                &contract_address_arbitrum_mainnet
            ),
            chain_config::create_base_indexer(postgres_client.clone()),
            chain_config::create_linea_indexer(postgres_client.clone()),
            chain_config::create_scroll_indexer(postgres_client.clone()),
            chain_config::create_zksync_indexer(postgres_client.clone()),
            chain_config::create_shape_indexer(postgres_client.clone())
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
        
        // Add a delay to prevent tight loop when all indexers are disabled (e.g., in tests)
        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
    }
}
