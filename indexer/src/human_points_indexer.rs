use crate::postgres::PostgresClient;
use chrono::DateTime;
use ethers::contract::EthEvent;
use ethers::core::types::{Address, Filter, Log, H256, U256};
use ethers::providers::{Middleware, Provider, StreamExt, Ws};
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Debug, Clone, EthEvent)]
#[ethevent(name = "Attested", abi = "Attested(address,address,bytes32,bytes32)")]
pub struct AttestedEvent {
    #[ethevent(indexed)]
    pub recipient: Address,
    #[ethevent(indexed)]
    pub attester: Address,
    pub uid: H256,
    #[ethevent(indexed)]
    pub schema_uid: H256,
}

#[derive(Debug, Clone, EthEvent)]
#[ethevent(name = "Transfer", abi = "Transfer(address,address,uint256)")]
pub struct TransferEvent {
    #[ethevent(indexed)]
    pub from: Address,
    #[ethevent(indexed)]
    pub to: Address,
    #[ethevent(indexed)]
    pub token_id: U256,
}

#[derive(Debug, Clone)]
pub struct ChainConfig {
    pub chain_id: u32,
    pub chain_name: String,
    pub eas_address: Address,
    pub schema_uid: H256,
}

pub struct HumanPointsIndexer {
    provider: Arc<Provider<Ws>>,
    postgres_client: Arc<PostgresClient>,
    chain_configs: HashMap<u32, ChainConfig>,
    human_id_address: Address,
    current_chain_id: u32,
}

impl HumanPointsIndexer {
    pub fn new(
        provider: Arc<Provider<Ws>>,
        postgres_client: Arc<PostgresClient>,
        current_chain_id: u32,
    ) -> Self {
        let mut chain_configs = HashMap::new();
        
        // Optimism
        chain_configs.insert(10, ChainConfig {
            chain_id: 10,
            chain_name: "Optimism".to_string(),
            eas_address: "0x4200000000000000000000000000000000000021".parse().unwrap(),
            schema_uid: "0xda0257756063c891659fed52fd36ef7557f7b45d66f59645fd3c3b263b747254".parse().unwrap(),
        });
        
        // Linea
        chain_configs.insert(59144, ChainConfig {
            chain_id: 59144,
            chain_name: "Linea".to_string(),
            eas_address: "0xaEF4103A04090071165F78D45D83A0C0782c2B2a".parse().unwrap(),
            schema_uid: "0xa15ea01b11913fd412243156b40a8d5102ee9784172f82f9481e4c953fdd516d".parse().unwrap(),
        });
        
        // Arbitrum
        chain_configs.insert(42161, ChainConfig {
            chain_id: 42161,
            chain_name: "Arbitrum".to_string(),
            eas_address: "0xbD75f629A22Dc1ceD33dDA0b68c546A1c035c458".parse().unwrap(),
            schema_uid: "0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse().unwrap(),
        });
        
        // zkSync Era
        chain_configs.insert(324, ChainConfig {
            chain_id: 324,
            chain_name: "zkSync Era".to_string(),
            eas_address: "0x21d8d4eE83b80bc0Cc0f2B7df3117Cf212d02901".parse().unwrap(),
            schema_uid: "0xb68405dffc0b727188de5a3af2ecbbc544ab01aef5353409c5006ffff342d143".parse().unwrap(),
        });
        
        // Scroll
        chain_configs.insert(534352, ChainConfig {
            chain_id: 534352,
            chain_name: "Scroll".to_string(),
            eas_address: "0xC47300428b6AD2c7D03BB76D05A176058b47E6B0".parse().unwrap(),
            schema_uid: "0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse().unwrap(),
        });
        
        // Shape
        chain_configs.insert(360, ChainConfig {
            chain_id: 360,
            chain_name: "Shape".to_string(),
            eas_address: "0x4200000000000000000000000000000000000021".parse().unwrap(),
            schema_uid: "0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse().unwrap(),
        });
        
        // Base
        chain_configs.insert(8453, ChainConfig {
            chain_id: 8453,
            chain_name: "Base".to_string(),
            eas_address: "0x4200000000000000000000000000000000000021".parse().unwrap(),
            schema_uid: "0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912".parse().unwrap(),
        });

        let human_id_address = "0x2AA822e264F8cc31A2b9C22f39e5551241e94DfB".parse().unwrap();

        Self {
            provider,
            postgres_client,
            chain_configs,
            human_id_address,
            current_chain_id,
        }
    }

    pub async fn run(self: Arc<Self>) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        println!("Starting Human Points indexer for chain {}", self.current_chain_id);

        let mut tasks = vec![];

        // Only index EAS events if this chain has EAS configured
        if let Some(chain_config) = self.chain_configs.get(&self.current_chain_id) {
            let self_clone = Arc::clone(&self);
            let chain_config = chain_config.clone();
            tasks.push(tokio::spawn(async move {
                self_clone.index_eas_events(chain_config).await
            }));
        }

        // Only index Human ID events on Optimism
        if self.current_chain_id == 10 {
            let self_clone = Arc::clone(&self);
            tasks.push(tokio::spawn(async move {
                self_clone.index_human_id_events().await
            }));
        }

        // Wait for all tasks
        for task in tasks {
            task.await??;
        }

        Ok(())
    }

    async fn index_eas_events(&self, chain_config: ChainConfig) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        println!("Starting EAS indexer for {} (chain {})", chain_config.chain_name, chain_config.chain_id);

        // Get current block
        let current_block = self.provider.get_block_number().await?;
        
        // Create filter for Attested events with the specific schema UID
        let filter = Filter::new()
            .address(chain_config.eas_address)
            .event("Attested(address,address,bytes32,bytes32)")
            .topic3(chain_config.schema_uid)
            .from_block(current_block);

        let mut stream = self.provider.watch(&filter).await?;

        while let Some(log) = stream.next().await {
            match self.process_eas_log(log, &chain_config).await {
                Ok(_) => {},
                Err(e) => eprintln!("Error processing EAS log: {:?}", e),
            }
        }

        Ok(())
    }

    async fn index_human_id_events(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        println!("Starting Human ID indexer on Optimism");

        // Get current block
        let current_block = self.provider.get_block_number().await?;
        
        // Create filter for Transfer events
        let filter = Filter::new()
            .address(self.human_id_address)
            .event("Transfer(address,address,uint256)")
            .from_block(current_block);

        let mut stream = self.provider.watch(&filter).await?;

        while let Some(log) = stream.next().await {
            match self.process_human_id_log(log).await {
                Ok(_) => {},
                Err(e) => eprintln!("Error processing Human ID log: {:?}", e),
            }
        }

        Ok(())
    }

    async fn process_eas_log(&self, log: Log, chain_config: &ChainConfig) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let event: AttestedEvent = ethers::contract::parse_log(log.clone())?;
        
        // Get block timestamp
        let block = self.provider.get_block(log.block_number.unwrap()).await?
            .ok_or("Block not found")?;
        let timestamp = block.timestamp;

        let address = format!("{:#x}", event.recipient).to_lowercase();
        let tx_hash = format!("{:#x}", log.transaction_hash.unwrap());

        println!("Processing passport mint for {} on {} (tx: {})", address, chain_config.chain_name, tx_hash);

        let timestamp_dt = DateTime::from_timestamp(timestamp.as_u64() as i64, 0).unwrap();
        
        self.postgres_client.insert_human_points(
            &address,
            "PMT",
            timestamp_dt,
            &tx_hash,
            Some(chain_config.chain_id as i32),
        ).await?;

        Ok(())
    }

    async fn process_human_id_log(&self, log: Log) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let event: TransferEvent = ethers::contract::parse_log(log.clone())?;
        
        // Only process mints (from address is zero)
        if event.from != Address::zero() {
            return Ok(());
        }

        // Get block timestamp
        let block = self.provider.get_block(log.block_number.unwrap()).await?
            .ok_or("Block not found")?;
        let timestamp = block.timestamp;

        let address = format!("{:#x}", event.to).to_lowercase();
        let tx_hash = format!("{:#x}", log.transaction_hash.unwrap());

        println!("Processing Human ID SBT mint for {} (tx: {})", address, tx_hash);

        let timestamp_dt = DateTime::from_timestamp(timestamp.as_u64() as i64, 0).unwrap();
        
        self.postgres_client.insert_human_points(
            &address,
            "HIM",
            timestamp_dt,
            &tx_hash,
            Some(10), // Optimism chain ID
        ).await?;

        Ok(())
    }
}