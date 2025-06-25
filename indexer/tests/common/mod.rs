pub mod event_emitter;

use ethers::prelude::*;
use std::sync::Arc;
use tokio_postgres::{Client, NoTls};
use event_emitter::EventEmitter;
use std::time::Duration;

pub struct TestContext {
    pub staking_emitter: EventEmitter,
    pub eas_emitter: EventEmitter,
    pub human_id_emitter: EventEmitter,
    pub db_client: Client,
    pub provider: Arc<Provider<Http>>,
}

impl TestContext {
    pub async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        // Connect to the existing Anvil instance started by the test script
        let rpc_url = std::env::var("INDEXER_OPTIMISM_RPC_URL")
            .unwrap_or_else(|_| "http://localhost:8545".to_string());
        
        // Create provider to connect to existing Anvil
        let provider = Provider::<Http>::try_from(rpc_url)?;
        let provider = Arc::new(provider);
        
        // Get the deployed contract addresses from environment variables
        // These are set by the test script after deploying the contracts
        let staking_address = std::env::var("INDEXER_OPTIMISM_STAKING_CONTRACT")
            .expect("INDEXER_OPTIMISM_STAKING_CONTRACT must be set by test script")
            .parse::<Address>()?;
            
        let eas_address = std::env::var("INDEXER_OPTIMISM_EAS_CONTRACT")
            .expect("INDEXER_OPTIMISM_EAS_CONTRACT must be set by test script")
            .parse::<Address>()?;
            
        let human_id_address = std::env::var("INDEXER_OPTIMISM_HUMAN_ID_CONTRACT")
            .expect("INDEXER_OPTIMISM_HUMAN_ID_CONTRACT must be set by test script")
            .parse::<Address>()?;
        
        // Create EventEmitter instances for the deployed contracts
        let staking_emitter = EventEmitter::new(staking_address, provider.clone())?;
        let eas_emitter = EventEmitter::new(eas_address, provider.clone())?;
        let human_id_emitter = EventEmitter::new(human_id_address, provider.clone())?;
        
        // Get DB client with savepoint
        let db_client = setup_test_db().await?;
        
        Ok(Self {
            staking_emitter,
            eas_emitter,
            human_id_emitter,
            db_client,
            provider,
        })
    }
    
    pub async fn wait_for_indexer(&self, duration: std::time::Duration) {
        tokio::time::sleep(duration).await;
    }
    
    pub async fn cleanup(self) -> Result<(), Box<dyn std::error::Error>> {
        // Rollback DB changes to the savepoint
        self.db_client.execute("ROLLBACK TO SAVEPOINT test_start", &[]).await?;
        
        Ok(())
    }
}

async fn setup_test_db() -> Result<Client, Box<dyn std::error::Error>> {
    let db_url = std::env::var("DB_URL")
        .expect("DB_URL must be set by test script");
    
    let (client, connection) = tokio_postgres::connect(&db_url, NoTls).await?;
    
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            eprintln!("Database connection error: {}", e);
        }
    });
    
    // Start transaction with savepoint
    client.execute("BEGIN", &[]).await?;
    client.execute("SAVEPOINT test_start", &[]).await?;
    
    Ok(client)
}

// Re-export ethers types that tests will need
pub use ethers::types::{Address, H256, U256};
pub use ethers::utils::parse_ether;