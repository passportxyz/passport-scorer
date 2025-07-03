use ethers::core::types::Address;
use eyre::Result;
use std::sync::Arc;

use crate::{
    postgres::PostgresClient,
    unified_indexer::{ChainConfig, ContractConfig, ContractType, UnifiedChainIndexer},
    utils::{get_env, get_env_optional, get_env_with_default},
};

// Default start blocks for chains (same as Human Points contract start blocks)
const OPTIMISM_DEFAULT_START_BLOCK: &str = "138123811";
const ARBITRUM_DEFAULT_START_BLOCK: &str = "355019547";
const OPTIMISM_SEPOLIA_DEFAULT_START_BLOCK: &str = "29876951";
const BASE_DEFAULT_START_BLOCK: &str = "32528526";
const LINEA_DEFAULT_START_BLOCK: &str = "20777084";
const SCROLL_DEFAULT_START_BLOCK: &str = "17073673";
const ZKSYNC_DEFAULT_START_BLOCK: &str = "63028818";
const SHAPE_DEFAULT_START_BLOCK: &str = "15050964";

pub async fn create_legacy_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    // For legacy indexer, keep the explicit enabled flag since it shares RPC with ethereum
    if get_env_with_default("INDEXER_LEGACY_ENABLED", "") != "true" {
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
    // Check if RPC URL is provided, if not, skip this indexer
    let optimism_rpc_url = match get_env_optional("INDEXER_OPTIMISM_RPC_URL") {
        Some(url) => url,
        None => return Ok(()),
    };

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
    if get_env_with_default("HUMAN_POINTS_ENABLED", "") == "true" {
        // EAS contract for Passport mint on Optimism
        let eas_address = get_env_with_default(
            "INDEXER_OPTIMISM_EAS_CONTRACT",
            "0x4200000000000000000000000000000000000021"
        ).parse()?;

        contracts.push(ContractConfig {
            address: eas_address,
            start_block: OPTIMISM_DEFAULT_START_BLOCK.parse().unwrap(), // July 7th, 2025
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0xda0257756063c891659fed52fd36ef7557f7b45d66f59645fd3c3b263b747254".parse()?,
            ),
        });

        // Human ID SBT contract on Optimism
        let human_id_address = get_env_with_default(
            "INDEXER_OPTIMISM_HUMAN_ID_CONTRACT",
            "0x2AA822e264F8cc31A2b9C22f39e5551241e94DfB"
        ).parse()?;

        contracts.push(ContractConfig {
            address: human_id_address,
            start_block: OPTIMISM_DEFAULT_START_BLOCK.parse().unwrap(), // July 7th, 2025
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
    // Check if RPC URL is provided, if not, skip this indexer
    let arbitrum_rpc_url = match get_env_optional("INDEXER_ARBITRUM_RPC_URL") {
        Some(url) => url,
        None => return Ok(()),
    };
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
    if get_env_with_default("HUMAN_POINTS_ENABLED", "") == "true" {
        // EAS contract for Passport mint on Arbitrum
        let eas_address = get_env_with_default(
            "INDEXER_ARBITRUM_EAS_CONTRACT",
            "0xbD75f629A22Dc1ceD33dDA0b68c546A1c035c458"
        ).parse()?;

        contracts.push(ContractConfig {
            address: eas_address,
            start_block: ARBITRUM_DEFAULT_START_BLOCK.parse().unwrap(), // July 7th, 2025
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
    // Check if RPC URL is provided, if not, skip this indexer
    let op_sepolia_rpc_url = match get_env_optional("INDEXER_OPTIMISM_SEPOLIA_RPC_URL") {
        Some(url) => url,
        None => return Ok(()),
    };
    let op_sepolia_start_block = get_env_with_default("INDEXER_OPTIMISM_SEPOLIA_START_BLOCK", OPTIMISM_SEPOLIA_DEFAULT_START_BLOCK)
        .parse::<u64>()
        .unwrap();

    let mut contracts = vec![ContractConfig {
        address: *contract_address,
        start_block: op_sepolia_start_block,
        contract_type: ContractType::Staking,
        schema_uid: None,
    }];

    if get_env_with_default("HUMAN_POINTS_ENABLED", "") == "true" {
        // EAS contract for Passport mint on Optimism Sepolia
        contracts.push(ContractConfig {
            address: "0x4200000000000000000000000000000000000021".parse()?,
            start_block: op_sepolia_start_block,
            contract_type: ContractType::PassportMint,
            schema_uid: Some(
                "0x81d8758ccd97bbeea7642df29001f6046a676b3c24f808c4297db5ee36838dd8".parse()?,
            ),
        });
    }

    let chain_config = ChainConfig {
        rpc_url: op_sepolia_rpc_url,
        contracts: contracts,
    };

    let indexer = UnifiedChainIndexer::new(chain_config, postgres_client).await?;
    indexer.run().await
}

pub async fn create_base_indexer(postgres_client: Arc<PostgresClient>) -> Result<()> {
    // Check if RPC URL is provided, if not, skip this indexer
    let base_rpc_url = match get_env_optional("INDEXER_BASE_RPC_URL") {
        Some(url) => url,
        None => return Ok(()),
    };
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env_with_default("HUMAN_POINTS_ENABLED", "") == "true" {
        // EAS contract for Passport mint on Base
        contracts.push(ContractConfig {
            address: "0x4200000000000000000000000000000000000021".parse()?,
            start_block: BASE_DEFAULT_START_BLOCK.parse().unwrap(), // July 7th, 2025
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
    // Check if RPC URL is provided, if not, skip this indexer
    let linea_rpc_url = match get_env_optional("INDEXER_LINEA_RPC_URL") {
        Some(url) => url,
        None => return Ok(()),
    };
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env_with_default("HUMAN_POINTS_ENABLED", "") == "true" {
        // EAS contract for Passport mint on Linea
        contracts.push(ContractConfig {
            address: "0xaEF4103A04090071165F78D45D83A0C0782c2B2a".parse()?,
            start_block: LINEA_DEFAULT_START_BLOCK.parse().unwrap(), // July 7th, 2025
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
    // Check if RPC URL is provided, if not, skip this indexer
    let scroll_rpc_url = match get_env_optional("INDEXER_SCROLL_RPC_URL") {
        Some(url) => url,
        None => return Ok(()),
    };
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env_with_default("HUMAN_POINTS_ENABLED", "") == "true" {
        // EAS contract for Passport mint on Scroll
        contracts.push(ContractConfig {
            address: "0xC47300428b6AD2c7D03BB76D05A176058b47E6B0".parse()?,
            start_block: SCROLL_DEFAULT_START_BLOCK.parse().unwrap(), // July 7th, 2025
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
    // Check if RPC URL is provided, if not, skip this indexer
    let zksync_rpc_url = match get_env_optional("INDEXER_ZKSYNC_RPC_URL") {
        Some(url) => url,
        None => return Ok(()),
    };
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env_with_default("HUMAN_POINTS_ENABLED", "") == "true" {
        // EAS contract for Passport mint on zkSync Era
        contracts.push(ContractConfig {
            address: "0x21d8d4eE83b80bc0Cc0f2B7df3117Cf212d02901".parse()?,
            start_block: ZKSYNC_DEFAULT_START_BLOCK.parse().unwrap(), // July 7th, 2025
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
    // Check if RPC URL is provided, if not, skip this indexer
    let shape_rpc_url = match get_env_optional("INDEXER_SHAPE_RPC_URL") {
        Some(url) => url,
        None => return Ok(()),
    };
    let mut contracts = vec![];

    // Add Human Points contracts if enabled
    if get_env_with_default("HUMAN_POINTS_ENABLED", "") == "true" {
        // EAS contract for Passport mint on Shape
        contracts.push(ContractConfig {
            address: "0x4200000000000000000000000000000000000021".parse()?,
            start_block: SHAPE_DEFAULT_START_BLOCK.parse().unwrap(), // July 7th, 2025
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
