use ethers::{
    providers::{JsonRpcClient, Provider, ProviderError, PubsubClient, SubscriptionStream},
    types::U256,
};
use serde::{de::DeserializeOwned, Serialize};
use std::{
    fmt::Debug,
    sync::{
        atomic::{AtomicU64, AtomicUsize, Ordering},
        Arc,
    },
    time::{Duration, Instant},
};
use async_trait::async_trait;
use futures::{stream::BoxStream, StreamExt};
use serde_json::Value;
use tokio::sync::RwLock;

/// Statistics for WebSocket connection
#[derive(Debug, Clone)]
pub struct WsStats {
    pub total_requests: usize,
    pub total_responses: usize,
    pub total_errors: usize,
    pub connection_drops: usize,
    pub last_error: Option<String>,
    pub last_error_time: Option<Instant>,
    pub connection_start: Instant,
    pub last_successful_request: Option<Instant>,
}

/// A WebSocket provider wrapper that adds comprehensive debugging
pub struct DebugWsProvider<P> {
    inner: P,
    stats: Arc<RwLock<WsStats>>,
    request_counter: Arc<AtomicU64>,
    debug_enabled: bool,
    chain_id: u32,
}

impl<P> DebugWsProvider<P> {
    pub fn new(inner: P, chain_id: u32, debug_enabled: bool) -> Self {
        Self {
            inner,
            stats: Arc::new(RwLock::new(WsStats {
                total_requests: 0,
                total_responses: 0,
                total_errors: 0,
                connection_drops: 0,
                last_error: None,
                last_error_time: None,
                connection_start: Instant::now(),
                last_successful_request: None,
            })),
            request_counter: Arc::new(AtomicU64::new(0)),
            debug_enabled,
            chain_id,
        }
    }

    pub async fn get_stats(&self) -> WsStats {
        self.stats.read().await.clone()
    }

    async fn log_request(&self, method: &str, params: &Value) {
        let mut stats = self.stats.write().await;
        stats.total_requests += 1;
        
        if self.debug_enabled {
            let request_id = self.request_counter.fetch_add(1, Ordering::SeqCst);
            eprintln!(
                "[Chain {}] Request #{}: {} {}",
                self.chain_id, request_id, method,
                if method == "eth_subscribe" {
                    format!("params: {}", serde_json::to_string(params).unwrap_or_default())
                } else {
                    String::new()
                }
            );
        }
    }

    async fn log_response(&self, method: &str, success: bool, error_msg: Option<String>) {
        let mut stats = self.stats.write().await;
        
        if success {
            stats.total_responses += 1;
            stats.last_successful_request = Some(Instant::now());
            
            if self.debug_enabled {
                eprintln!("[Chain {}] Response: {} - SUCCESS", self.chain_id, method);
            }
        } else {
            stats.total_errors += 1;
            if let Some(ref msg) = error_msg {
                stats.last_error = Some(msg.clone());
                stats.last_error_time = Some(Instant::now());
                
                // Check if this is a connection drop
                if msg.contains("closed") || msg.contains("disconnected") || msg.contains("reset") {
                    stats.connection_drops += 1;
                }
            }
            
            eprintln!(
                "[Chain {}] ERROR: {} - {}",
                self.chain_id, method,
                error_msg.as_deref().unwrap_or("Unknown error")
            );
        }
    }

    pub async fn print_diagnostics(&self) {
        let stats = self.stats.read().await;
        let uptime = stats.connection_start.elapsed();
        
        eprintln!("\n=== WebSocket Diagnostics for Chain {} ===", self.chain_id);
        eprintln!("Uptime: {:?}", uptime);
        eprintln!("Total Requests: {}", stats.total_requests);
        eprintln!("Total Responses: {}", stats.total_responses);
        eprintln!("Total Errors: {}", stats.total_errors);
        eprintln!("Connection Drops: {}", stats.connection_drops);
        
        if stats.total_requests > 0 {
            let success_rate = (stats.total_responses as f64 / stats.total_requests as f64) * 100.0;
            eprintln!("Success Rate: {:.2}%", success_rate);
        }
        
        if let Some(ref last_error) = stats.last_error {
            eprintln!("Last Error: {}", last_error);
            if let Some(last_error_time) = stats.last_error_time {
                eprintln!("Last Error Time: {:?} ago", last_error_time.elapsed());
            }
        }
        
        if let Some(last_success) = stats.last_successful_request {
            eprintln!("Last Successful Request: {:?} ago", last_success.elapsed());
        }
        
        eprintln!("=====================================\n");
    }
}

#[async_trait]
impl<P: JsonRpcClient> JsonRpcClient for DebugWsProvider<P> {
    type Error = P::Error;

    async fn request<T, R>(&self, method: &str, params: T) -> Result<R, Self::Error>
    where
        T: Debug + Serialize + Send + Sync,
        R: DeserializeOwned + Send,
    {
        let params_value = serde_json::to_value(&params).unwrap_or(Value::Null);
        self.log_request(method, &params_value).await;
        
        let start = Instant::now();
        let result = self.inner.request(method, params).await;
        let duration = start.elapsed();
        
        match &result {
            Ok(_) => {
                self.log_response(method, true, None).await;
                if self.debug_enabled && duration > Duration::from_secs(5) {
                    eprintln!(
                        "[Chain {}] WARNING: {} took {:?}",
                        self.chain_id, method, duration
                    );
                }
            }
            Err(e) => {
                let error_msg = format!("{:?}", e);
                self.log_response(method, false, Some(error_msg)).await;
            }
        }
        
        result
    }
}

#[async_trait]
impl<P: PubsubClient> PubsubClient for DebugWsProvider<P> {
    type NotificationStream = P::NotificationStream;

    fn subscribe<T: Into<U256>>(&self, id: T) -> Result<Self::NotificationStream, Self::Error> {
        self.inner.subscribe(id)
    }

    fn unsubscribe<T: Into<U256>>(&self, id: T) -> Result<(), Self::Error> {
        self.inner.unsubscribe(id)
    }
}

/// Create a debug provider that wraps the WebSocket connection
pub async fn create_debug_provider(
    rpc_url: &str,
    chain_id: u32,
    debug_enabled: bool,
) -> Result<Provider<DebugWsProvider<ethers::providers::Ws>>, Box<dyn std::error::Error>> {
    use ethers::providers::Ws;
    
    eprintln!("[Chain {}] Creating debug WebSocket connection to {}", chain_id, rpc_url);
    
    // Create inner WebSocket provider with reconnection
    let inner = Ws::connect_with_reconnects(rpc_url, 3).await?;
    
    // Wrap it with our debug provider
    let debug_provider = DebugWsProvider::new(inner, chain_id, debug_enabled);
    
    // Return as Provider
    Ok(Provider::new(debug_provider))
}

/// Monitor WebSocket health and automatically print diagnostics
pub async fn monitor_ws_health<P: JsonRpcClient + 'static>(
    provider: Arc<Provider<DebugWsProvider<P>>>,
    interval_secs: u64,
) {
    let mut interval = tokio::time::interval(Duration::from_secs(interval_secs));
    
    loop {
        interval.tick().await;
        
        if let Some(debug_provider) = provider.as_ref().inner() {
            debug_provider.print_diagnostics().await;
        }
    }
}