use ethers::{
    contract::abigen,
    core::types::Address,
    providers::{Provider, Middleware, Ws, StreamExt},
};
use std::sync::Arc;

abigen!(IdentityStaking, "./src/IdentityStaking.json",);

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // First, let's create a custom WebSocket that logs messages
    println!("Connecting to Optimism WebSocket...");
    
    let ws_url = "wss://opt-mainnet.g.alchemy.com/v2/jVBAR31G_KehyFy3xnaef-plbATRQoB-";
    let contract_address: Address = "0xf58Bb56E6e6EA7834478b470615e037df825C442".parse()?;
    
    // Unfortunately, ethers-rs doesn't expose the raw WebSocket messages easily
    // But we can use a proxy or packet capture. For now, let's at least show
    // what the library is doing at a high level
    
    let provider = Provider::<Ws>::connect(ws_url).await?;
    let client = Arc::new(provider);
    
    // Get current block
    let current_block = client.get_block_number().await?;
    println!("Current block: {}", current_block);
    
    let contract = IdentityStaking::new(contract_address, client.clone());
    
    println!("\nCreating event filter...");
    println!("Contract address: {}", contract_address);
    println!("From block: {}", current_block);
    
    // This is the exact code from staking_indexer.rs
    let future_events = contract.events().from_block(current_block);
    
    println!("\nCalling .stream() - this will send eth_subscribe...");
    let mut stream = future_events.stream().await?.with_meta();
    
    println!("Stream created! Subscription is active.");
    println!("\nBased on the ethers-rs source code, the JSON-RPC request sent was:");
    println!(r#"{{
  "jsonrpc": "2.0",
  "id": <some_id>,
  "method": "eth_subscribe",
  "params": [
    "logs",
    {{
      "address": "{}",
      "fromBlock": "0x{:x}"
    }}
  ]
}}"#, contract_address, current_block);
    
    println!("\nWaiting for events (10 seconds)...");
    
    // Listen for a few events
    let mut count = 0;
    let timeout = tokio::time::sleep(tokio::time::Duration::from_secs(10));
    tokio::pin!(timeout);
    
    loop {
        tokio::select! {
            _ = &mut timeout => {
                println!("Timeout reached, closing stream");
                break;
            }
            Some(event_result) = stream.next() => {
                match event_result {
                    Ok((event, meta)) => {
                        count += 1;
                        println!("\nEvent #{} received:", count);
                        println!("  Block: {}", meta.block_number);
                        println!("  Transaction: {:?}", meta.transaction_hash);
                        match event {
                            IdentityStakingEvents::SelfStakeFilter(e) => {
                                println!("  Type: SelfStake");
                                println!("  Staker: {}", e.staker);
                            }
                            IdentityStakingEvents::CommunityStakeFilter(e) => {
                                println!("  Type: CommunityStake");
                                println!("  Staker: {}, Stakee: {}", e.staker, e.stakee);
                            }
                            _ => println!("  Type: Other event"),
                        }
                    }
                    Err(e) => {
                        eprintln!("Error receiving event: {}", e);
                    }
                }
            }
        }
    }
    
    println!("\nDone!");
    Ok(())
}