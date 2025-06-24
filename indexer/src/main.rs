mod human_points_indexer;
mod legacy_staking_indexer;
mod postgres;
mod sql_generation;
mod staking_indexer;
mod unified_indexer;
mod utils;

use dotenv::dotenv;
use ethers::core::types::Address;
use eyre::Result;
use futures::try_join;
use legacy_staking_indexer::LegacyStakingIndexer;
use postgres::PostgresClient;
use std::sync::Arc;
use unified_indexer::{ChainConfig, ContractConfig, ContractType, UnifiedChainIndexer};
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
        let contract_address_arbitrum_mainnet = get_env("STAKING_CONTRACT_ADDRESS_ARBITRUM_MAINNET")
            .parse::<Address>()
            .unwrap();

        let postgres_client = Arc::new(postgres_client);
        
        match try_join!(
            run_legacy_indexer(postgres_client.clone()),
            run_unified_ethereum_indexer(postgres_client.clone(), &contract_address_eth_mainnet),
            run_unified_optimism_indexer(postgres_client.clone(), &contract_address_op_mainnet),
            run_unified_optimism_sepolia_indexer(postgres_client.clone(), &contract_address_op_sepolia),
            run_unified_arbitrum_indexer(postgres_client.clone(), &contract_address_arbitrum_mainnet),
            run_unified_base_indexer(postgres_client.clone()),
            run_unified_linea_indexer(postgres_client.clone()),
            run_unified_scroll_indexer(postgres_client.clone()),
            run_unified_zksync_indexer(postgres_client.clone()),
            run_unified_shape_indexer(postgres_client.clone())
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

async fn run_legacy_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    if get_env("INDEXER_LEGACY_ENABLED") != "true" {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("INDEXER_ETHEREUM_RPC_URL");
    let legacy_staking_indexer = LegacyStakingIndexer::new((*postgres_client).clone(), &ethereum_rpc_url);
    legacy_staking_indexer.listen_with_timeout_reset().await
}

async fn run_unified_ethereum_indexer(
    postgres_client: Arc<PostgresClient>,
    contract_address: &Address,
) -> Result<()> {
    if get_env("INDEXER_ETHEREUM_ENABLED") != "true" {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("INDEXER_ETHEREUM_RPC_URL");
    let ethereum_start_block = get_env("INDEXER_ETHEREUM_START_BLOCK")
        .parse::<u64>()
        .unwrap();
    
    let chain_config = ChainConfig {
        chain_id: 1, // Ethereum mainnet
        rpc_url: ethereum_rpc_url,
        contracts: vec![
            ContractConfig {
                address: *contract_address,
                start_block: ethereum_start_block,
                contract_type: ContractType::Staking,
                schema_uid: None,
            },
        ],
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

async fn run_unified_optimism_indexer(
    postgres_client: Arc<PostgresClient>,
    contract_address: &Address,
) -> Result<()> {
    if get_env("INDEXER_OPTIMISM_ENABLED") != "true" {
        return Ok(());
    }

    let optimism_rpc_url = get_env("INDEXER_OPTIMISM_RPC_URL");
    let optimism_start_block = get_env("INDEXER_OPTIMISM_START_BLOCK")
        .parse::<u64>()
        .unwrap();
    
    let mut contracts = vec![
        ContractConfig {
            address: *contract_address,
            start_block: optimism_start_block,
            contract_type: ContractType::Staking,
            schema_uid: None,
        },
    ];
    
    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // Passport mint on Optimism
        contracts.push(ContractConfig {
            address: "0x4200000000000000000000000000000000000021".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some("0xda0257756063c891659fed52fd36ef7557f7b45d66f59645fd3c3b263b747254".parse()?),
        });
        
        // Human ID SBT on Optimism
        contracts.push(ContractConfig {
            address: "0x2AA822e264F8cc31A2b9C22f39e5551241e94DfB".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::HumanIdMint,
            schema_uid: None,
        });
    }
    
    let chain_config = ChainConfig {
        chain_id: 10, // Optimism mainnet
        rpc_url: optimism_rpc_url,
        contracts,
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

async fn run_unified_arbitrum_indexer(
    postgres_client: Arc<PostgresClient>,
    contract_address: &Address,
) -> Result<()> {
    if get_env("INDEXER_ARBITRUM_ENABLED") != "true" {
        return Ok(());
    }

    let arbitrum_rpc_url = get_env("INDEXER_ARBITRUM_RPC_URL");
    let arbitrum_start_block = get_env("INDEXER_ARBITRUM_START_BLOCK")
        .parse::<u64>()
        .unwrap();
    
    let mut contracts = vec![
        ContractConfig {
            address: *contract_address,
            start_block: arbitrum_start_block,
            contract_type: ContractType::Staking,
            schema_uid: None,
        },
    ];
    
    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // Passport mint on Arbitrum
        contracts.push(ContractConfig {
            address: "0xbD75f629A22Dc1ceD33dDA0b68c546A1c035c458".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some("0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse()?),
        });
    }
    
    let chain_config = ChainConfig {
        chain_id: 42161, // Arbitrum mainnet
        rpc_url: arbitrum_rpc_url,
        contracts,
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}


async fn run_unified_optimism_sepolia_indexer(
    postgres_client: Arc<PostgresClient>,
    contract_address: &Address,
) -> Result<()> {
    if get_env("INDEXER_OPTIMISM_SEPOLIA_ENABLED") != "true" {
        return Ok(());
    }

    let op_sepolia_rpc_url = get_env("INDEXER_OPTIMISM_SEPOLIA_RPC_URL");
    let op_sepolia_start_block = get_env("INDEXER_OPTIMISM_SEPOLIA_START_BLOCK")
        .parse::<u64>()
        .unwrap();
    
    let chain_config = ChainConfig {
        chain_id: 11155420, // OP Sepolia
        rpc_url: op_sepolia_rpc_url,
        contracts: vec![
            ContractConfig {
                address: *contract_address,
                start_block: op_sepolia_start_block,
                contract_type: ContractType::Staking,
                schema_uid: None,
            },
        ],
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

async fn run_unified_base_indexer(
    postgres_client: Arc<PostgresClient>,
) -> Result<()> {
    if get_env("INDEXER_BASE_ENABLED") != "true" {
        return Ok(());
    }

    let base_rpc_url = get_env("INDEXER_BASE_RPC_URL");
    
    let mut contracts = vec![];
    
    // Add staking contract if exists
    if let Ok(contract_address) = get_env("STAKING_CONTRACT_ADDRESS_BASE").parse::<Address>() {
        let base_start_block = get_env("INDEXER_BASE_START_BLOCK")
            .parse::<u64>()
            .unwrap_or(0);
        contracts.push(ContractConfig {
            address: contract_address,
            start_block: base_start_block,
            contract_type: ContractType::Staking,
            schema_uid: None,
        });
    }
    
    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // Passport mint on Base
        contracts.push(ContractConfig {
            address: "0x4200000000000000000000000000000000000021".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some("0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse()?),
        });
    }
    
    if contracts.is_empty() {
        return Ok(());
    }
    
    let chain_config = ChainConfig {
        chain_id: 8453, // Base mainnet
        rpc_url: base_rpc_url,
        contracts,
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

async fn run_unified_linea_indexer(
    postgres_client: Arc<PostgresClient>,
) -> Result<()> {
    if get_env("INDEXER_LINEA_ENABLED") != "true" {
        return Ok(());
    }

    let linea_rpc_url = get_env("INDEXER_LINEA_RPC_URL");
    
    let mut contracts = vec![];
    
    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // Passport mint on Linea
        contracts.push(ContractConfig {
            address: "0xaEF4103A04090071165F78D45D83A0C0782c2B2a".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some("0xa15ea01b11913fd412243156b40a8d5102ee9784172f82f9481e4c953fdd516d".parse()?),
        });
    }
    
    if contracts.is_empty() {
        return Ok(());
    }
    
    let chain_config = ChainConfig {
        chain_id: 59144, // Linea mainnet
        rpc_url: linea_rpc_url,
        contracts,
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

async fn run_unified_scroll_indexer(
    postgres_client: Arc<PostgresClient>,
) -> Result<()> {
    if get_env("INDEXER_SCROLL_ENABLED") != "true" {
        return Ok(());
    }

    let scroll_rpc_url = get_env("INDEXER_SCROLL_RPC_URL");
    
    let mut contracts = vec![];
    
    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // Passport mint on Scroll
        contracts.push(ContractConfig {
            address: "0xC47300428b6AD2c7D03BB76D05A176058b47E6B0".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some("0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse()?),
        });
    }
    
    if contracts.is_empty() {
        return Ok(());
    }
    
    let chain_config = ChainConfig {
        chain_id: 534352, // Scroll mainnet
        rpc_url: scroll_rpc_url,
        contracts,
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

async fn run_unified_zksync_indexer(
    postgres_client: Arc<PostgresClient>,
) -> Result<()> {
    if get_env("INDEXER_ZKSYNC_ENABLED") != "true" {
        return Ok(());
    }

    let zksync_rpc_url = get_env("INDEXER_ZKSYNC_RPC_URL");
    
    let mut contracts = vec![];
    
    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // Passport mint on zkSync Era
        contracts.push(ContractConfig {
            address: "0x21d8d4eE83b80bc0Cc0f2B7df3117Cf212d02901".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some("0xb68405dffc0b727188de5a3af2ecbbc544ab01aef5353409c5006ffff342d143".parse()?),
        });
    }
    
    if contracts.is_empty() {
        return Ok(());
    }
    
    let chain_config = ChainConfig {
        chain_id: 324, // zkSync Era mainnet
        rpc_url: zksync_rpc_url,
        contracts,
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

async fn run_unified_shape_indexer(
    postgres_client: Arc<PostgresClient>,
) -> Result<()> {
    if get_env("INDEXER_SHAPE_ENABLED") != "true" {
        return Ok(());
    }

    let shape_rpc_url = get_env("INDEXER_SHAPE_RPC_URL");
    
    let mut contracts = vec![];
    
    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // Passport mint on Shape
        contracts.push(ContractConfig {
            address: "0x4200000000000000000000000000000000000021".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some("0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse()?),
        });
    }
    
    if contracts.is_empty() {
        return Ok(());
    }
    
    let chain_config = ChainConfig {
        chain_id: 360, // Shape mainnet
        rpc_url: shape_rpc_url,
        contracts,
    };
    
    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}
