pub mod event_emitter;

use ethers::prelude::*;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use tokio_postgres::{Client, NoTls};
use event_emitter::EventEmitter;

// Helper function to get test table names
fn get_table_name(base_name: &str) -> String {
    if let Ok(suffix) = std::env::var("TEST_TABLE_SUFFIX") {
        format!("{}{}", base_name, suffix)
    } else {
        base_name.to_string()
    }
}

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
        // Note: The tests use HTTP provider while indexer uses WebSocket
        let anvil_port = std::env::var("ANVIL_PORT").unwrap_or_else(|_| "8545".to_string());
        let rpc_url = format!("http://localhost:{}", anvil_port);
        
        // Create provider to connect to existing Anvil
        let provider = Provider::<Http>::try_from(rpc_url)?;
        
        // Test the provider connection
        let _block_number = provider.get_block_number().await?;
        
        let provider = Arc::new(provider);
        
        // Get the deployed contract addresses from environment variables
        // These are set by the test script after deploying the contracts
        let staking_address = std::env::var("INDEXER_OPTIMISM_STAKING_CONTRACT")
            .expect("INDEXER_OPTIMISM_STAKING_CONTRACT must be set by test script");
        let staking_address = staking_address.parse::<Address>()?;
            
        let eas_address = std::env::var("INDEXER_OPTIMISM_EAS_CONTRACT")
            .expect("INDEXER_OPTIMISM_EAS_CONTRACT must be set by test script");
        let eas_address = eas_address.parse::<Address>()?;
            
        let human_id_address = std::env::var("INDEXER_OPTIMISM_HUMAN_ID_CONTRACT")
            .expect("INDEXER_OPTIMISM_HUMAN_ID_CONTRACT must be set by test script");
        let human_id_address = human_id_address.parse::<Address>()?;
        
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
    
    pub async fn wait_for_event_count(&self, table: &str, expected_count: i64, timeout: std::time::Duration) -> Result<(), Box<dyn std::error::Error>> {
        let start = std::time::Instant::now();
        loop {
            let count_result = self.db_client
                .query_one(&format!("SELECT COUNT(*) FROM {}", get_table_name(table)), &[])
                .await?;
            let count: i64 = count_result.get(0);
            
            if count >= expected_count {
                return Ok(());
            }
            
            if start.elapsed() > timeout {
                return Err(format!("Timeout waiting for {} events in {}, found only {}", expected_count, table, count).into());
            }
            
            tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        }
    }
    
    pub async fn wait_for_stake_event_count(&self, addresses: &[&str], expected_count: i64, timeout: std::time::Duration) -> Result<(), Box<dyn std::error::Error>> {
        let start = std::time::Instant::now();
        loop {
            let count_result = self.db_client
                .query_one(
                    &format!("SELECT COUNT(*) FROM {} WHERE staker = ANY($1) OR stakee = ANY($1)", get_table_name("stake_stakeevent")),
                    &[&addresses]
                )
                .await?;
            let count: i64 = count_result.get(0);
            
            if count >= expected_count {
                return Ok(());
            }
            
            if start.elapsed() > timeout {
                return Err(format!("Timeout waiting for {} stake events for addresses {:?}, found only {}", expected_count, addresses, count).into());
            }
            
            tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        }
    }
    
    pub async fn wait_for_human_points_count(&self, address: &str, expected_count: i64, timeout: std::time::Duration) -> Result<(), Box<dyn std::error::Error>> {
        let start = std::time::Instant::now();
        loop {
            let count_result = self.db_client
                .query_one(
                    &format!("SELECT COUNT(*) FROM {} WHERE address = $1", get_table_name("registry_humanpoints")),
                    &[&address]
                )
                .await?;
            let count: i64 = count_result.get(0);
            
            if count >= expected_count {
                return Ok(());
            }
            
            if start.elapsed() > timeout {
                return Err(format!("Timeout waiting for {} human points for address {}, found only {}", expected_count, address, count).into());
            }
            
            tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        }
    }
    
    
    pub async fn cleanup(self) -> Result<(), Box<dyn std::error::Error>> {
        // Rollback DB changes to the savepoint to preserve original data
        self.db_client.execute("ROLLBACK TO SAVEPOINT test_start", &[]).await?;
        self.db_client.execute("COMMIT", &[]).await?;
        
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
    
    // Test the connection with a simple query
    let row = client.query_one("SELECT 1", &[]).await?;
    let _test_val: i32 = row.get(0);
    
    // No need for transactions or truncation - we're using separate test tables
    
    Ok(client)
}

// Re-export ethers types that tests will need
pub use ethers::types::{Address, H256, U256};
pub use ethers::utils::parse_ether;