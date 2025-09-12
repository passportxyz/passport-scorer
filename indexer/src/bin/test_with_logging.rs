use ethers::{
    contract::abigen,
    core::types::Address,
    providers::{Provider, Middleware, Ws, StreamExt},
};
use std::sync::Arc;

abigen!(IdentityStaking, "../IdentityStaking.json",);

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Enable debug logging for ethers-rs
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("debug")).init();
    
    println!("Connecting to Optimism WebSocket with debug logging enabled...");
    println!("This will show internal ethers-rs operations\n");
    
    let ws_url = "wss://opt-mainnet.g.alchemy.com/v2/jVBAR31G_KehyFy3xnaef-plbATRQoB-";
    let contract_address: Address = "0xf58Bb56E6e6EA7834478b470615e037df825C442".parse()?;
    
    let provider = Provider::<Ws>::connect(ws_url).await?;
    let client = Arc::new(provider);
    
    let current_block = client.get_block_number().await?;
    println!("Current block: {}", current_block);
    
    let contract = IdentityStaking::new(contract_address, client.clone());
    
    println!("\nCreating event stream (this will trigger eth_subscribe)...");
    let future_events = contract.events().from_block(current_block);
    let mut stream = future_events.stream().await?.with_meta();
    
    println!("\nStream created! Waiting for events...");
    
    // Wait for one event or timeout
    let timeout = tokio::time::sleep(tokio::time::Duration::from_secs(10));
    tokio::pin!(timeout);
    
    tokio::select! {
        _ = timeout => {
            println!("Timeout - no events received");
        }
        Some(event_result) = stream.next() => {
            match event_result {
                Ok((event, meta)) => {
                    println!("\nEvent received at block {}", meta.block_number);
                    match event {
                        IdentityStakingEvents::SelfStakeFilter(_) => println!("Event type: SelfStake"),
                        IdentityStakingEvents::CommunityStakeFilter(_) => println!("Event type: CommunityStake"),
                        _ => println!("Event type: Other"),
                    }
                }
                Err(e) => eprintln!("Error: {}", e),
            }
        }
    }
    
    Ok(())
}