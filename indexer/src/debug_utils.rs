use crate::debug_ws_provider::{create_debug_provider, DebugWsProvider};
use ethers::providers::{Provider, Ws};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::time::sleep;

/// Enhanced WebSocket connection with comprehensive error handling and diagnostics
pub async fn create_debug_rpc_connection(
    rpc_url: &String,
    chain_id: u32,
) -> Arc<Provider<DebugWsProvider<Ws>>> {
    let mut num_retries = 0;
    let delay_base: u64 = 2;
    let max_consecutive_failures = 10;
    let mut consecutive_failures = 0;
    let mut last_error_details = String::new();

    loop {
        let attempt_start = Instant::now();
        
        eprintln!(
            "[Chain {}] Connection attempt #{} to {}",
            chain_id, num_retries + 1, rpc_url
        );

        match create_debug_provider(rpc_url, chain_id, true).await {
            Ok(provider) => {
                eprintln!(
                    "[Chain {}] Successfully connected after {:?}",
                    chain_id,
                    attempt_start.elapsed()
                );
                
                // Test the connection with a simple request
                match provider.get_block_number().await {
                    Ok(block) => {
                        eprintln!("[Chain {}] Connection verified, current block: {}", chain_id, block);
                        consecutive_failures = 0;
                        return Arc::new(provider);
                    }
                    Err(e) => {
                        eprintln!(
                            "[Chain {}] Connection test failed: {:?}",
                            chain_id, e
                        );
                        last_error_details = format!("Connection test failed: {:?}", e);
                    }
                }
            }
            Err(e) => {
                let error_str = format!("{:?}", e);
                consecutive_failures += 1;
                
                // Detailed error analysis
                let error_category = categorize_ws_error(&error_str);
                
                eprintln!(
                    "[Chain {}] Connection failed (attempt #{}, consecutive failures: {})",
                    chain_id, num_retries + 1, consecutive_failures
                );
                eprintln!("[Chain {}] Error category: {:?}", chain_id, error_category);
                eprintln!("[Chain {}] Error details: {}", chain_id, error_str);
                
                last_error_details = error_str;
                
                if consecutive_failures >= max_consecutive_failures {
                    eprintln!(
                        "[Chain {}] CRITICAL: {} consecutive connection failures. Last error: {}",
                        chain_id, consecutive_failures, last_error_details
                    );
                    
                    // Wait longer before continuing
                    sleep(Duration::from_secs(60)).await;
                    consecutive_failures = 0; // Reset counter after long wait
                }
            }
        }

        // Exponential backoff with jitter
        let base_delay = delay_base.pow(num_retries.min(6));
        let jitter = rand::random::<u64>() % (base_delay / 2);
        let delay = base_delay + jitter;
        
        eprintln!(
            "[Chain {}] Waiting {} seconds before retry...",
            chain_id, delay
        );
        
        sleep(Duration::from_secs(delay)).await;
        
        num_retries += 1;
        
        // Log periodic summaries
        if num_retries > 0 && num_retries % 10 == 0 {
            eprintln!(
                "[Chain {}] ERROR SUMMARY: {} total attempts, {} consecutive failures",
                chain_id, num_retries, consecutive_failures
            );
            eprintln!("[Chain {}] Last error: {}", chain_id, last_error_details);
        }
    }
}

#[derive(Debug)]
pub enum WsErrorCategory {
    ConnectionRefused,
    Timeout,
    TlsError,
    DnsError,
    ProtocolError,
    AuthenticationError,
    RateLimitError,
    UnexpectedClose,
    Unknown,
}

/// Categorize WebSocket errors for better diagnostics
pub fn categorize_ws_error(error_str: &str) -> WsErrorCategory {
    let error_lower = error_str.to_lowercase();
    
    if error_lower.contains("refused") || error_lower.contains("connection refused") {
        WsErrorCategory::ConnectionRefused
    } else if error_lower.contains("timeout") || error_lower.contains("timed out") {
        WsErrorCategory::Timeout
    } else if error_lower.contains("tls") || error_lower.contains("ssl") || error_lower.contains("certificate") {
        WsErrorCategory::TlsError
    } else if error_lower.contains("dns") || error_lower.contains("resolve") || error_lower.contains("lookup") {
        WsErrorCategory::DnsError
    } else if error_lower.contains("protocol") || error_lower.contains("handshake") {
        WsErrorCategory::ProtocolError
    } else if error_lower.contains("401") || error_lower.contains("403") || error_lower.contains("unauthorized") {
        WsErrorCategory::AuthenticationError
    } else if error_lower.contains("429") || error_lower.contains("rate") || error_lower.contains("limit") {
        WsErrorCategory::RateLimitError
    } else if error_lower.contains("closed") || error_lower.contains("disconnected") || error_lower.contains("eof") {
        WsErrorCategory::UnexpectedClose
    } else {
        WsErrorCategory::Unknown
    }
}

/// Test WebSocket connection with detailed diagnostics
pub async fn test_ws_connection(rpc_url: &String, chain_id: u32) -> Result<(), Box<dyn std::error::Error>> {
    eprintln!("\n=== Testing WebSocket Connection ===");
    eprintln!("URL: {}", rpc_url);
    eprintln!("Chain ID: {}", chain_id);
    
    // Test 1: Basic connection
    eprintln!("\n1. Testing basic connection...");
    let provider = create_debug_provider(rpc_url, chain_id, true).await?;
    eprintln!("✓ Connection established");
    
    // Test 2: Simple RPC call
    eprintln!("\n2. Testing eth_blockNumber...");
    let start = Instant::now();
    let block = provider.get_block_number().await?;
    eprintln!("✓ Current block: {} (took {:?})", block, start.elapsed());
    
    // Test 3: Subscription
    eprintln!("\n3. Testing eth_subscribe...");
    use ethers::providers::{Middleware, StreamExt};
    let mut stream = provider.subscribe_blocks().await?;
    eprintln!("✓ Subscription created");
    
    // Wait for one block
    eprintln!("\n4. Waiting for one block...");
    let timeout = sleep(Duration::from_secs(30));
    tokio::pin!(timeout);
    
    tokio::select! {
        Some(block) = stream.next() => {
            eprintln!("✓ Received block: {}", block.number.unwrap_or_default());
        }
        _ = timeout => {
            eprintln!("⚠ No blocks received in 30 seconds");
        }
    }
    
    // Print final diagnostics
    if let Some(debug_provider) = provider.as_ref().inner() {
        debug_provider.print_diagnostics().await;
    }
    
    eprintln!("\n✓ All tests completed");
    Ok(())
}