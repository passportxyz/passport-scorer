use ethers::core::types::Address;
use eyre::Result;
use std::sync::Arc;

use crate::{
    postgres::PostgresClient,
    unified_indexer::{ChainConfig, ContractConfig, ContractType, UnifiedChainIndexer},
    utils::get_env,
};

pub async fn create_legacy_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    if get_env("INDEXER_LEGACY_ENABLED") != "true" {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("INDEXER_ETHEREUM_RPC_URL");
    let legacy_staking_indexer = crate::legacy_staking_indexer::LegacyStakingIndexer::new(
        (*postgres_client).clone(),
        &ethereum_rpc_url,
    );
    legacy_staking_indexer.listen_with_timeout_reset().await
}

pub async fn create_ethereum_indexer(
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
        rpc_url: ethereum_rpc_url,
        contracts: vec![ContractConfig {
            address: *contract_address,
            start_block: ethereum_start_block,
            contract_type: ContractType::Staking,
            schema_uid: None,
        }],
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_optimism_indexer(
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

    let mut contracts = vec![ContractConfig {
        address: *contract_address,
        start_block: optimism_start_block,
        contract_type: ContractType::Staking,
        schema_uid: None,
    }];

    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // EAS contract for Passport mint on Optimism
        let eas_address = std::env::var("INDEXER_OPTIMISM_EAS_CONTRACT")
            .unwrap_or_else(|_| "0x4200000000000000000000000000000000000021".to_string())
            .parse()?;
        
        contracts.push(ContractConfig {
            address: eas_address,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0xda0257756063c891659fed52fd36ef7557f7b45d66f59645fd3c3b263b747254".parse()?,
            ),
        });

        // Human ID SBT contract on Optimism
        let human_id_address = std::env::var("INDEXER_OPTIMISM_HUMAN_ID_CONTRACT")
            .unwrap_or_else(|_| "0x2AA822e264F8cc31A2b9C22f39e5551241e94DfB".to_string())
            .parse()?;
            
        contracts.push(ContractConfig {
            address: human_id_address,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::HumanIdMint,
            schema_uid: None,
        });
    }

    let chain_config = ChainConfig {
        rpc_url: optimism_rpc_url,
        contracts,
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_arbitrum_indexer(
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

    let mut contracts = vec![ContractConfig {
        address: *contract_address,
        start_block: arbitrum_start_block,
        contract_type: ContractType::Staking,
        schema_uid: None,
    }];

    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // EAS contract for Passport mint on Arbitrum
        let eas_address = std::env::var("INDEXER_ARBITRUM_EAS_CONTRACT")
            .unwrap_or_else(|_| "0xbD75f629A22Dc1ceD33dDA0b68c546A1c035c458".to_string())
            .parse()?;
            
        contracts.push(ContractConfig {
            address: eas_address,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse()?,
            ),
        });
    }

    let chain_config = ChainConfig {
        rpc_url: arbitrum_rpc_url,
        contracts,
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_optimism_sepolia_indexer(
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
        rpc_url: op_sepolia_rpc_url,
        contracts: vec![ContractConfig {
            address: *contract_address,
            start_block: op_sepolia_start_block,
            contract_type: ContractType::Staking,
            schema_uid: None,
        }],
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_base_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    if get_env("INDEXER_BASE_ENABLED") != "true" {
        return Ok(());
    }

    let base_rpc_url = get_env("INDEXER_BASE_RPC_URL");
    let mut contracts = vec![];

    // Add staking contract if configured
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
        // EAS contract for Passport mint on Base
        contracts.push(ContractConfig {
            address: "0x4200000000000000000000000000000000000021".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse()?,
            ),
        });
    }

    if contracts.is_empty() {
        return Ok(());
    }

    let chain_config = ChainConfig {
        rpc_url: base_rpc_url,
        contracts,
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_linea_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    if get_env("INDEXER_LINEA_ENABLED") != "true" {
        return Ok(());
    }

    let linea_rpc_url = get_env("INDEXER_LINEA_RPC_URL");
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // EAS contract for Passport mint on Linea
        contracts.push(ContractConfig {
            address: "0xaEF4103A04090071165F78D45D83A0C0782c2B2a".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0xa15ea01b11913fd412243156b40a8d5102ee9784172f82f9481e4c953fdd516d".parse()?,
            ),
        });
    }

    if contracts.is_empty() {
        return Ok(());
    }

    let chain_config = ChainConfig {
        rpc_url: linea_rpc_url,
        contracts,
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_scroll_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    if get_env("INDEXER_SCROLL_ENABLED") != "true" {
        return Ok(());
    }

    let scroll_rpc_url = get_env("INDEXER_SCROLL_RPC_URL");
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // EAS contract for Passport mint on Scroll
        contracts.push(ContractConfig {
            address: "0xC47300428b6AD2c7D03BB76D05A176058b47E6B0".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse()?,
            ),
        });
    }

    if contracts.is_empty() {
        return Ok(());
    }

    let chain_config = ChainConfig {
        rpc_url: scroll_rpc_url,
        contracts,
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_zksync_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    if get_env("INDEXER_ZKSYNC_ENABLED") != "true" {
        return Ok(());
    }

    let zksync_rpc_url = get_env("INDEXER_ZKSYNC_RPC_URL");
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // EAS contract for Passport mint on zkSync Era
        contracts.push(ContractConfig {
            address: "0x21d8d4eE83b80bc0Cc0f2B7df3117Cf212d02901".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0xb68405dffc0b727188de5a3af2ecbbc544ab01aef5353409c5006ffff342d143".parse()?,
            ),
        });
    }

    if contracts.is_empty() {
        return Ok(());
    }

    let chain_config = ChainConfig {
        rpc_url: zksync_rpc_url,
        contracts,
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_shape_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    if get_env("INDEXER_SHAPE_ENABLED") != "true" {
        return Ok(());
    }

    let shape_rpc_url = get_env("INDEXER_SHAPE_RPC_URL");
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env("HUMAN_POINTS_ENABLED") == "true" {
        // EAS contract for Passport mint on Shape
        contracts.push(ContractConfig {
            address: "0x4200000000000000000000000000000000000021".parse()?,
            start_block: 0, // TODO: Add actual deployment block
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse()?,
            ),
        });
    }

    if contracts.is_empty() {
        return Ok(());
    }

    let chain_config = ChainConfig {
        rpc_url: shape_rpc_url,
        contracts,
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}
