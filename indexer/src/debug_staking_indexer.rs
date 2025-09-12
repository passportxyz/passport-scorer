use crate::{
    debug_utils::create_debug_rpc_connection,
    postgres::PostgresClient,
    utils::{StakeAmountOperation, StakeEventType},
};
use ethers::{
    contract::{abigen, LogMeta},
    core::types::Address,
    providers::{Middleware, StreamExt},
};
use eyre::Result;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::time::sleep;

abigen!(IdentityStaking, "./src/IdentityStaking.json",);

/// Enhanced StakingIndexer with WebSocket debugging
pub struct DebugStakingIndexer<'a> {
    postgres_client: PostgresClient,
    rpc_url: &'a String,
    chain_id: u32,
    start_block: u64,
    contract_address: &'a Address,
    last_event_time: Instant,
    events_since_last_check: u64,
}

impl<'a> DebugStakingIndexer<'a> {
    pub async fn new(
        postgres_client: PostgresClient,
        rpc_url: &'a String,
        chain_id: u32,
        start_block: u64,
        contract_address: &'a Address,
    ) -> Result<Self> {
        Ok(Self {
            postgres_client,
            rpc_url,
            chain_id,
            start_block,
            contract_address,
            last_event_time: Instant::now(),
            events_since_last_check: 0,
        })
    }

    pub async fn listen_with_enhanced_debugging(&mut self) -> Result<()> {
        loop {
            eprintln!(
                "\n[Chain {}] Starting new indexing cycle at {}",
                self.chain_id,
                chrono::Local::now().format("%Y-%m-%d %H:%M:%S")
            );

            match self.listen_for_events_with_diagnostics().await {
                Ok(_) => {
                    eprintln!(
                        "[Chain {}] Indexing cycle completed normally",
                        self.chain_id
                    );
                }
                Err(e) => {
                    let error_str = format!("{:?}", e);
                    eprintln!(
                        "[Chain {}] ERROR in indexing cycle: {}",
                        self.chain_id, error_str
                    );
                    
                    // Analyze error type
                    if error_str.contains("websocket") || error_str.contains("closed") {
                        eprintln!(
                            "[Chain {}] WebSocket error detected. Full error context:",
                            self.chain_id
                        );
                        eprintln!("{:#?}", e);
                        
                        // Wait before reconnecting
                        eprintln!(
                            "[Chain {}] Waiting 30 seconds before reconnection attempt...",
                            self.chain_id
                        );
                        sleep(Duration::from_secs(30)).await;
                    }
                }
            }
        }
    }

    async fn listen_for_events_with_diagnostics(&mut self) -> Result<()> {
        // Create debug-enabled connection
        let client = create_debug_rpc_connection(self.rpc_url, self.chain_id).await;
        
        // Get current block with error handling
        let current_block = match client.get_block_number().await {
            Ok(block) => {
                eprintln!("[Chain {}] Current block: {}", self.chain_id, block);
                block.as_u64()
            }
            Err(e) => {
                eprintln!(
                    "[Chain {}] Failed to get current block: {:?}",
                    self.chain_id, e
                );
                return Err(eyre::eyre!("Failed to get current block: {:?}", e));
            }
        };

        let id_staking_contract = IdentityStaking::new(*self.contract_address, client.clone());
        
        // Get starting block
        let query_start_block = self.get_query_start_block().await?;
        eprintln!(
            "[Chain {}] Starting from block {} (current: {})",
            self.chain_id, query_start_block, current_block
        );

        // Query historical events first (if needed)
        if query_start_block < current_block {
            self.query_historical_events(
                &id_staking_contract,
                query_start_block,
                current_block,
                &client
            ).await?;
        }

        // Subscribe to future events
        eprintln!(
            "[Chain {}] Creating event subscription from block {}...",
            self.chain_id, current_block
        );
        
        let future_events = id_staking_contract.events().from_block(current_block);
        
        let stream_result = future_events.stream().await;
        let mut stream = match stream_result {
            Ok(s) => {
                eprintln!("[Chain {}] ✓ Event stream created successfully", self.chain_id);
                s.with_meta()
            }
            Err(e) => {
                eprintln!("[Chain {}] Failed to create event stream: {:?}", self.chain_id, e);
                return Err(eyre::eyre!("Failed to create event stream: {:?}", e));
            }
        };

        eprintln!("[Chain {}] Listening for events...", self.chain_id);
        
        let mut last_heartbeat = Instant::now();
        let heartbeat_interval = Duration::from_secs(60);
        let mut events_received = 0u64;

        loop {
            // Check if we need to print heartbeat
            if last_heartbeat.elapsed() > heartbeat_interval {
                eprintln!(
                    "[Chain {}] Heartbeat: Still listening... ({} events in last minute)",
                    self.chain_id, events_received
                );
                events_received = 0;
                last_heartbeat = Instant::now();
                
                // Also check connection health
                match client.get_block_number().await {
                    Ok(block) => {
                        eprintln!("[Chain {}] Connection healthy, current block: {}", self.chain_id, block);
                    }
                    Err(e) => {
                        eprintln!("[Chain {}] Health check failed: {:?}", self.chain_id, e);
                        return Err(eyre::eyre!("Connection health check failed: {:?}", e));
                    }
                }
            }

            // Wait for events with timeout
            let timeout = sleep(Duration::from_secs(300)); // 5 minute timeout
            tokio::pin!(timeout);

            tokio::select! {
                Some(event_result) = stream.next() => {
                    match event_result {
                        Ok((event, meta)) => {
                            events_received += 1;
                            self.events_since_last_check += 1;
                            self.last_event_time = Instant::now();
                            
                            eprintln!(
                                "[Chain {}] Event received: block {}, tx {}",
                                self.chain_id,
                                meta.block_number,
                                format!("{:?}", meta.transaction_hash)
                            );
                            
                            if let Err(e) = self.process_staking_event(&event, &meta, &client).await {
                                eprintln!(
                                    "[Chain {}] Error processing event: {:?}",
                                    self.chain_id, e
                                );
                            }
                        }
                        Err(e) => {
                            eprintln!(
                                "[Chain {}] Error receiving event from stream: {:?}",
                                self.chain_id, e
                            );
                            return Err(eyre::eyre!("Stream error: {:?}", e));
                        }
                    }
                }
                _ = timeout => {
                    eprintln!(
                        "[Chain {}] No events received in 5 minutes. Last event was {:?} ago",
                        self.chain_id,
                        self.last_event_time.elapsed()
                    );
                    
                    // Try a health check
                    match client.get_block_number().await {
                        Ok(block) => {
                            eprintln!(
                                "[Chain {}] Connection still alive, current block: {}. Continuing...",
                                self.chain_id, block
                            );
                        }
                        Err(e) => {
                            eprintln!(
                                "[Chain {}] Connection appears dead: {:?}",
                                self.chain_id, e
                            );
                            return Err(eyre::eyre!("Connection timeout: {:?}", e));
                        }
                    }
                }
            }
        }
    }

    async fn get_query_start_block(&self) -> Result<u64> {
        let requested_start_block = self
            .postgres_client
            .get_requested_start_block(self.chain_id)
            .await?;

        if requested_start_block > 0 {
            self.postgres_client
                .acknowledge_requested_start_block(self.chain_id)
                .await?;
            return Ok(requested_start_block);
        } else {
            let latest_logged_block = self.postgres_client.get_latest_block(self.chain_id).await?;

            if latest_logged_block > 0 {
                return Ok(latest_logged_block + 1);
            } else {
                return Ok(self.start_block);
            }
        }
    }

    async fn query_historical_events(
        &self,
        contract: &IdentityStaking<Arc<dyn Middleware>>,
        start_block: u64,
        end_block: u64,
        client: &Arc<dyn Middleware>,
    ) -> Result<()> {
        eprintln!(
            "[Chain {}] Querying historical events from {} to {}",
            self.chain_id, start_block, end_block
        );

        let mut current = start_block;
        while current < end_block {
            let to = std::cmp::min(current + 999, end_block);
            
            eprintln!(
                "[Chain {}] Querying blocks {} to {}...",
                self.chain_id, current, to
            );

            match contract
                .events()
                .from_block(current)
                .to_block(to)
                .query_with_meta()
                .await
            {
                Ok(events) => {
                    eprintln!(
                        "[Chain {}] Found {} events in blocks {}-{}",
                        self.chain_id,
                        events.len(),
                        current,
                        to
                    );
                    
                    for (event, meta) in events.iter() {
                        self.process_staking_event(&event, &meta, &client).await?;
                    }

                    self.postgres_client
                        .update_last_checked_block(self.chain_id, &to)
                        .await?;

                    current = to + 1;
                }
                Err(e) => {
                    eprintln!(
                        "[Chain {}] Error querying events for blocks {}-{}: {:?}",
                        self.chain_id, current, to, e
                    );
                    return Err(eyre::eyre!("Failed to query historical events: {:?}", e));
                }
            }
        }

        Ok(())
    }

    async fn process_staking_event(
        &self,
        event: &IdentityStakingEvents,
        meta: &LogMeta,
        client: &Arc<dyn Middleware>,
    ) -> Result<()> {
        let block_number = meta.block_number.as_u64();
        let tx_hash = format!("{:?}", meta.transaction_hash);

        match event {
            IdentityStakingEvents::SelfStakeFilter(event) => {
                self.process_self_stake_event(&event, block_number, &tx_hash, &client).await
            }
            IdentityStakingEvents::CommunityStakeFilter(event) => {
                self.process_community_stake_event(&event, block_number, &tx_hash, &client).await
            }
            IdentityStakingEvents::SelfStakeWithdrawnFilter(event) => {
                self.process_self_stake_withdrawn_event(&event, block_number, &tx_hash).await
            }
            IdentityStakingEvents::CommunityStakeWithdrawnFilter(event) => {
                self.process_community_stake_withdrawn_event(&event, block_number, &tx_hash).await
            }
            IdentityStakingEvents::SlashFilter(event) => {
                self.process_slash_event(&event, block_number, &tx_hash).await
            }
            IdentityStakingEvents::ReleaseFilter(event) => {
                self.process_release_event(&event, block_number, &tx_hash).await
            }
            _ => {
                eprintln!(
                    "[Chain {}] Unhandled event type in tx {}",
                    self.chain_id, tx_hash
                );
                Ok(())
            }
        }
    }

    // ... (implement the same process_* methods as in StakingIndexer)
    
    async fn get_timestamp_for_block_number(
        &self,
        block_number: u64,
        client: &Arc<dyn Middleware>,
    ) -> Result<u64> {
        if let Ok(Some(block)) = client.get_block(block_number).await {
            return Ok(block.timestamp.as_u64());
        }
        Err(eyre::eyre!(
            "Failed to fetch block timestamp for block {}",
            block_number
        ))
    }

    async fn process_self_stake_event(
        &self,
        event: &SelfStakeFilter,
        block_number: u64,
        tx_hash: &String,
        client: &Arc<dyn Middleware>,
    ) -> Result<()> {
        let timestamp = self
            .get_timestamp_for_block_number(block_number, client)
            .await?;

        if let Err(err) = self
            .postgres_client
            .add_or_extend_stake(
                &StakeEventType::SelfStake,
                self.chain_id,
                &event.staker,
                &event.staker,
                &event.amount,
                &event.unlock_time,
                &timestamp,
                &block_number,
                tx_hash,
            )
            .await
        {
            eprintln!(
                "[Chain {}] Failed to process self stake event: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    // ... (implement other process_* methods similarly)
}