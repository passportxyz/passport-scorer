pub mod event_emitter;

use ethers::prelude::*;
use std::process::{Child, Command};
use std::sync::Arc;
use tokio_postgres::{Client, NoTls};
use event_emitter::EventEmitter;

pub struct TestContext {
    pub anvil: AnvilInstance,
    pub event_emitter: EventEmitter,
    pub db_client: Client,
    pub indexer_handle: Option<tokio::task::JoinHandle<()>>,
    pub provider: Arc<Provider<Http>>,
}

impl TestContext {
    pub async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        // Start Anvil
        let anvil = AnvilInstance::new().await?;
        
        // Create provider
        let provider = Provider::<Http>::try_from(anvil.endpoint())?;
        let provider = Arc::new(provider);
        
        // Deploy event emitter contract
        let event_emitter = EventEmitter::deploy(provider.clone()).await?;
        
        // Get DB client with savepoint
        let db_client = setup_test_db().await?;
        
        Ok(Self {
            anvil,
            event_emitter,
            db_client,
            indexer_handle: None,
            provider,
        })
    }
    
    pub async fn start_indexer(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        let endpoint = self.anvil.endpoint();
        let db_url = std::env::var("DB_URL").unwrap_or_else(|_| {
            "postgresql://postgres:postgres@localhost/indexer_test".to_string()
        });
        let event_emitter_address = format!("{:?}", self.event_emitter.address);
        
        // Set environment variables for the indexer
        std::env::set_var("INDEXER_OPTIMISM_ENABLED", "true");
        std::env::set_var("INDEXER_OPTIMISM_RPC_URL", &endpoint);
        std::env::set_var("INDEXER_OPTIMISM_STAKING_CONTRACT", &event_emitter_address);
        std::env::set_var("INDEXER_OPTIMISM_EAS_CONTRACT", &event_emitter_address);
        std::env::set_var("INDEXER_OPTIMISM_HUMAN_ID_CONTRACT", &event_emitter_address);
        std::env::set_var("INDEXER_OPTIMISM_START_BLOCK", "0");
        std::env::set_var("HUMAN_POINTS_ENABLED", "true");
        
        // Disable other chains
        std::env::set_var("INDEXER_ARBITRUM_ENABLED", "false");
        std::env::set_var("INDEXER_BASE_ENABLED", "false");
        std::env::set_var("INDEXER_LINEA_ENABLED", "false");
        std::env::set_var("INDEXER_SCROLL_ENABLED", "false");
        std::env::set_var("INDEXER_ZKSYNC_ENABLED", "false");
        std::env::set_var("INDEXER_SHAPE_ENABLED", "false");
        
        // Parse DB URL for individual components
        let db_config = parse_db_url(&db_url)?;
        std::env::set_var("DB_USER", &db_config.user);
        std::env::set_var("DB_PASSWORD", &db_config.password);
        std::env::set_var("DB_HOST", &db_config.host);
        std::env::set_var("DB_PORT", &db_config.port);
        std::env::set_var("DB_NAME", &db_config.name);
        
        self.indexer_handle = Some(tokio::spawn(async move {
            // Start the actual production indexer
            if let Err(e) = indexer::main_loop().await {
                eprintln!("Indexer error: {:?}", e);
            }
        }));
        
        // Wait for indexer to be ready
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        
        Ok(())
    }
    
    pub async fn wait_for_indexer(&self, duration: std::time::Duration) {
        tokio::time::sleep(duration).await;
    }
    
    pub async fn cleanup(self) -> Result<(), Box<dyn std::error::Error>> {
        // Abort indexer
        if let Some(handle) = self.indexer_handle {
            handle.abort();
        }
        
        // Rollback DB changes
        self.db_client.execute("ROLLBACK", &[]).await?;
        
        // Anvil drops automatically
        Ok(())
    }
}

pub struct AnvilInstance {
    process: Child,
    port: u16,
}

impl AnvilInstance {
    pub async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let port = portpicker::pick_unused_port()
            .ok_or("Failed to find available port")?;
        
        let mut process = Command::new("anvil")
            .arg("--port").arg(port.to_string())
            .arg("--block-time").arg("1")
            .arg("--accounts").arg("10")
            .arg("--silent")
            .spawn()?;
        
        // Wait for Anvil to be ready
        wait_for_port(port).await?;
        
        Ok(Self { process, port })
    }
    
    pub fn endpoint(&self) -> String {
        format!("http://localhost:{}", self.port)
    }
}

impl Drop for AnvilInstance {
    fn drop(&mut self) {
        let _ = self.process.kill();
    }
}

async fn wait_for_port(port: u16) -> Result<(), Box<dyn std::error::Error>> {
    use std::time::Duration;
    
    for _ in 0..30 {
        if std::net::TcpStream::connect(format!("127.0.0.1:{}", port)).is_ok() {
            return Ok(());
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
    
    Err("Timeout waiting for port".into())
}

async fn setup_test_db() -> Result<Client, Box<dyn std::error::Error>> {
    let db_url = std::env::var("DB_URL")
        .unwrap_or_else(|_| "postgresql://postgres:postgres@localhost/indexer_test".to_string());
    
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

#[derive(Debug)]
struct DbConfig {
    user: String,
    password: String,
    host: String,
    port: String,
    name: String,
}

fn parse_db_url(url: &str) -> Result<DbConfig, Box<dyn std::error::Error>> {
    // postgresql://user:password@host:port/database
    let url = url.strip_prefix("postgresql://")
        .ok_or("Invalid DB URL format")?;
    
    let parts: Vec<&str> = url.split('@').collect();
    if parts.len() != 2 {
        return Err("Invalid DB URL format".into());
    }
    
    let auth_parts: Vec<&str> = parts[0].split(':').collect();
    if auth_parts.len() != 2 {
        return Err("Invalid DB URL auth format".into());
    }
    
    let user = auth_parts[0].to_string();
    let password = auth_parts[1].to_string();
    
    let location_parts: Vec<&str> = parts[1].split('/').collect();
    if location_parts.len() != 2 {
        return Err("Invalid DB URL location format".into());
    }
    
    let host_port: Vec<&str> = location_parts[0].split(':').collect();
    let host = host_port[0].to_string();
    let port = host_port.get(1).unwrap_or(&"5432").to_string();
    let name = location_parts[1].to_string();
    
    Ok(DbConfig {
        user,
        password,
        host,
        port,
        name,
    })
}

// Re-export ethers types that tests will need
pub use ethers::types::{Address, H256, U256};
pub use ethers::utils::parse_ether;