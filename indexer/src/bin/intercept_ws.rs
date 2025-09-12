use ethers::{
    contract::abigen,
    core::types::Address,
    providers::{Provider, Middleware, StreamExt, JsonRpcClient, ProviderError},
};
use serde::{Deserialize, Serialize};
use serde_json::value::RawValue;
use std::sync::Arc;
use async_trait::async_trait;
use tokio::net::TcpStream;
use tokio_tungstenite::{connect_async, tungstenite::Message, WebSocketStream, MaybeTlsStream};
use futures::stream::{SplitSink, SplitStream};
use futures::{SinkExt, StreamExt as FuturesStreamExt};

abigen!(IdentityStaking, "../IdentityStaking.json",);

// Custom WebSocket client that logs all messages
struct LoggingWsClient {
    id: std::sync::atomic::AtomicU64,
    sink: Arc<tokio::sync::Mutex<SplitSink<WebSocketStream<MaybeTlsStream<TcpStream>>, Message>>>,
    stream: Arc<tokio::sync::Mutex<SplitStream<WebSocketStream<MaybeTlsStream<TcpStream>>>>>,
}

#[derive(Debug, Serialize, Deserialize)]
struct JsonRpcRequest {
    jsonrpc: String,
    method: String,
    params: serde_json::Value,
    id: u64,
}

impl LoggingWsClient {
    async fn new(url: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let (ws_stream, _) = connect_async(url).await?;
        let (sink, stream) = ws_stream.split();
        
        Ok(Self {
            id: std::sync::atomic::AtomicU64::new(1),
            sink: Arc::new(tokio::sync::Mutex::new(sink)),
            stream: Arc::new(tokio::sync::Mutex::new(stream)),
        })
    }
}

#[async_trait]
impl JsonRpcClient for LoggingWsClient {
    type Error = ProviderError;

    async fn request<T, R>(&self, method: &str, params: T) -> Result<R, Self::Error>
    where
        T: Serialize + Send + Sync,
        R: for<'de> Deserialize<'de>,
    {
        let id = self.id.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        
        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            method: method.to_string(),
            params: serde_json::to_value(params).unwrap(),
            id,
        };
        
        let request_str = serde_json::to_string(&request).unwrap();
        
        // Log the outgoing request
        println!("\n=== OUTGOING JSON-RPC REQUEST ===");
        println!("{}", serde_json::to_string_pretty(&request).unwrap());
        
        // Send the request
        let mut sink = self.sink.lock().await;
        sink.send(Message::Text(request_str)).await.map_err(|e| {
            ProviderError::JsonRpcClientError(Box::new(e))
        })?;
        drop(sink);
        
        // Read the response
        let mut stream = self.stream.lock().await;
        while let Some(msg) = stream.next().await {
            match msg {
                Ok(Message::Text(text)) => {
                    let response: serde_json::Value = serde_json::from_str(&text).unwrap();
                    
                    // Check if this is our response
                    if response["id"].as_u64() == Some(id) {
                        println!("\n=== RESPONSE ===");
                        println!("{}", serde_json::to_string_pretty(&response).unwrap());
                        
                        if let Some(result) = response.get("result") {
                            return serde_json::from_value(result.clone())
                                .map_err(|e| ProviderError::JsonRpcClientError(Box::new(e)));
                        }
                    } else {
                        // This might be a subscription notification
                        if response.get("method").is_some() {
                            println!("\n=== SUBSCRIPTION NOTIFICATION ===");
                            println!("{}", serde_json::to_string_pretty(&response).unwrap());
                        }
                    }
                }
                _ => {}
            }
        }
        
        Err(ProviderError::JsonRpcClientError("No response".into()))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Creating custom logging WebSocket client...");
    
    let ws_url = "wss://opt-mainnet.g.alchemy.com/v2/jVBAR31G_KehyFy3xnaef-plbATRQoB-";
    let contract_address: Address = "0xf58Bb56E6e6EA7834478b470615e037df825C442".parse()?;
    
    let ws_client = LoggingWsClient::new(ws_url).await?;
    let provider = Provider::new(ws_client);
    let client = Arc::new(provider);
    
    let contract = IdentityStaking::new(contract_address, client.clone());
    
    println!("\nGetting current block number...");
    let current_block = client.get_block_number().await?;
    
    println!("\nCreating event stream...");
    let future_events = contract.events().from_block(current_block);
    
    println!("\nCalling .stream() - watch for the eth_subscribe request...");
    let _stream = future_events.stream().await?;
    
    // Keep the connection alive to see subscription notifications
    println!("\nKeeping connection alive for 5 seconds to see any notifications...");
    tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
    
    Ok(())
}