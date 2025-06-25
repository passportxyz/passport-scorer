use crate::{
    postgres::PostgresClient,
    utils::{create_rpc_connection, StakeAmountOperation, StakeEventType},
};
use chrono::DateTime;
use ethers::{
    contract::{abigen, EthEvent, EthLogDecode, LogMeta},
    core::types::{Address, Filter, Log, H256, U256},
    providers::{Middleware, Provider, StreamExt, Ws},
};
use eyre::Result;
use futures::try_join;
use std::{
    cmp::{max, min},
    sync::Arc,
};

// Import contract ABIs
abigen!(IdentityStaking, "./src/IdentityStaking.json",);

// EAS Attested event
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

// ERC721 Transfer event for Human ID SBT
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
pub struct ContractConfig {
    pub address: Address,
    pub start_block: u64,
    pub contract_type: ContractType,
    pub schema_uid: Option<H256>, // For EAS events
}

#[derive(Debug, Clone)]
pub enum ContractType {
    Staking,
    PassportMint,
    HumanIdMint,
}

#[derive(Debug, Clone)]
pub struct ChainConfig {
    pub rpc_url: String,
    pub contracts: Vec<ContractConfig>,
}

pub struct UnifiedChainIndexer {
    chain_config: ChainConfig,
    chain_id: u32,
    postgres_client: Arc<PostgresClient>,
}

async fn get_chain_id(rpc_url: &String) -> Result<u32> {
    let client = create_rpc_connection(rpc_url).await;
    let chain_id = client.get_chainid().await?;
    Ok(chain_id.as_u32())
}

impl UnifiedChainIndexer {
    pub async fn new(
        chain_config: ChainConfig,
        postgres_client: Arc<PostgresClient>,
    ) -> Result<Self> {
        let chain_id = get_chain_id(&chain_config.rpc_url).await?;

        Ok(Self {
            chain_config,
            chain_id,
            postgres_client,
        })
    }

    pub async fn run(&self) -> Result<()> {
        loop {
            let query_start_block = self.get_query_start_block().await?;

            println!(
                "Debug - Starting unified indexer for chain {} at block {}",
                self.chain_id, query_start_block
            );

            match try_join!(
                self.throw_when_no_events_logged(),
                self.throw_when_reindex_requested(),
                self.process_all_events(query_start_block),
            ) {
                Ok(_) => {
                    eprintln!(
                        "Warning - unified indexer ended without error for chain {}",
                        self.chain_id
                    );
                }
                Err(err) => {
                    if err
                        .to_string()
                        .contains("No events logged in the last 15 minutes")
                    {
                        eprintln!("Debug - resetting indexer due to no events logged in the last 15 minutes for chain {}", self.chain_id);
                    } else if err.to_string().contains("Reindex requested for chain") {
                        eprintln!(
                            "Debug - resetting indexer due to reindex requested for chain {}",
                            self.chain_id
                        );
                    } else {
                        eprintln!(
                            "Warning - unified indexer ended with error for chain {}, {:?}",
                            self.chain_id, err
                        );
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
                // Find the earliest start block from all configured contracts
                let earliest_start = self
                    .chain_config
                    .contracts
                    .iter()
                    .map(|c| c.start_block)
                    .min()
                    .unwrap_or(0);
                return Ok(earliest_start);
            }
        }
    }

    async fn throw_when_no_events_logged(&self) -> Result<()> {
        let mut timer_begin_event_count = self
            .postgres_client
            .get_total_event_count(self.chain_id)
            .await?;
        loop {
            // Sleep for 15 minutes
            tokio::time::sleep(tokio::time::Duration::from_secs(900)).await;

            let event_count = self
                .postgres_client
                .get_total_event_count(self.chain_id)
                .await?;

            if event_count <= timer_begin_event_count {
                return Err(eyre::eyre!(
                    "No events logged in the last 15 minutes for chain {}, total event count is {}",
                    self.chain_id,
                    event_count
                ));
            }

            timer_begin_event_count = event_count;
        }
    }

    async fn throw_when_reindex_requested(&self) -> Result<()> {
        loop {
            // Sleep for 1 minute
            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;

            let requested_start_block = self
                .postgres_client
                .get_requested_start_block(self.chain_id)
                .await?;

            if requested_start_block > 0 {
                return Err(eyre::eyre!(
                    "Reindex requested for chain {} at block {}",
                    self.chain_id,
                    requested_start_block
                ));
            }
        }
    }

    async fn get_current_block(&self) -> Result<u64> {
        // Recreating client here because when this fails (with local hardhat node)
        // it ruins the client and we need to recreate it
        let client = create_rpc_connection(&self.chain_config.rpc_url).await;
        let block_number = client.get_block_number().await?;
        Ok(block_number.as_u64())
    }

    async fn process_all_events(&self, initial_query_start_block: u64) -> Result<()> {
        let mut current_block: u64 = 2;
        if let Ok(block_number) = self.get_current_block().await {
            current_block = block_number;
        } else {
            eprintln!(
                "Warning - Failed to fetch current block number for chain {}",
                self.chain_id
            );
        }

        let provider = Arc::new(create_rpc_connection(&self.chain_config.rpc_url).await);
        let mut query_start_block = initial_query_start_block;

        // Process historical blocks
        while query_start_block < current_block - 1 {
            let query_end_block = min(query_start_block + 999, current_block - 1);
            eprintln!(
                "Debug - Querying past events for chain {} from block {} to block {}",
                self.chain_id, query_start_block, query_end_block
            );

            // Create a filter for all contract addresses
            let addresses: Vec<Address> = self
                .chain_config
                .contracts
                .iter()
                .map(|c| c.address)
                .collect();

            let filter = Filter::new()
                .address(addresses)
                .from_block(query_start_block)
                .to_block(query_end_block);

            let logs = match provider.get_logs(&filter).await {
                Ok(logs) => logs,
                Err(err) => {
                    return Err(eyre::eyre!(
                        "Error - Failed to query events for chain {}: {}, {}, {:?}",
                        self.chain_id,
                        query_start_block,
                        query_end_block,
                        err
                    ));
                }
            };

            for log in logs {
                self.route_log(log, &provider).await?;
            }

            self.postgres_client
                .update_last_checked_block(self.chain_id, &query_end_block)
                .await?;

            query_start_block = query_end_block + 1;
        }

        eprintln!(
            "Debug - Finished querying past events for chain {}",
            self.chain_id
        );

        // Watch for new events
        let from_block = max(query_start_block, current_block);

        eprintln!(
            "Debug - Listening for future events for chain {} from block {}",
            self.chain_id, from_block
        );

        let addresses: Vec<Address> = self
            .chain_config
            .contracts
            .iter()
            .map(|c| c.address)
            .collect();

        let filter = Filter::new().address(addresses).from_block(from_block);

        let mut stream = provider.watch(&filter).await?;

        while let Some(log) = stream.next().await {
            self.route_log(log, &provider).await?;
        }

        Ok(())
    }

    async fn route_log(&self, log: Log, provider: &Provider<Ws>) -> Result<()> {
        // Find which contract this log belongs to
        let contract_config = self
            .chain_config
            .contracts
            .iter()
            .find(|c| c.address == log.address)
            .ok_or_else(|| eyre::eyre!("Unknown contract address: {:?}", log.address))?;

        // Check if the event is from a block after the contract's deployment
        let block_number = log
            .block_number
            .ok_or_else(|| eyre::eyre!("Log missing block number"))?
            .as_u64();

        if block_number < contract_config.start_block {
            // Skip events before contract deployment
            return Ok(());
        }

        // Route based on contract type
        match &contract_config.contract_type {
            ContractType::Staking => self.process_staking_log(log, provider).await,
            ContractType::PassportMint => {
                self.process_passport_mint_log(log, contract_config, provider)
                    .await
            }
            ContractType::HumanIdMint => self.process_human_id_mint_log(log, provider).await,
        }
    }

    async fn process_staking_log(&self, log: Log, provider: &Provider<Ws>) -> Result<()> {
        // Parse as staking event
        let meta = LogMeta {
            block_number: log.block_number.unwrap(),
            block_hash: log.block_hash.unwrap(),
            transaction_hash: log.transaction_hash.unwrap(),
            transaction_index: log.transaction_index.unwrap(),
            log_index: log.log_index.unwrap(),
            address: log.address,
        };

        if let Ok(event) = IdentityStakingEvents::decode_log(&log.into()) {
            match event {
                IdentityStakingEvents::SelfStakeFilter(event) => {
                    self.process_self_stake_event(&event, &meta, provider).await
                }
                IdentityStakingEvents::CommunityStakeFilter(event) => {
                    self.process_community_stake_event(&event, &meta, provider)
                        .await
                }
                IdentityStakingEvents::SelfStakeWithdrawnFilter(event) => {
                    self.process_self_stake_withdrawn_event(&event, &meta).await
                }
                IdentityStakingEvents::CommunityStakeWithdrawnFilter(event) => {
                    self.process_community_stake_withdrawn_event(&event, &meta)
                        .await
                }
                IdentityStakingEvents::SlashFilter(event) => {
                    self.process_slash_event(&event, &meta).await
                }
                IdentityStakingEvents::ReleaseFilter(event) => {
                    self.process_release_event(&event, &meta).await
                }
                _ => {
                    eprintln!(
                        "Debug - Unhandled staking event: tx_hash: {:?}, chain_id: {}",
                        meta.transaction_hash, self.chain_id
                    );
                    Ok(())
                }
            }
        } else {
            Ok(())
        }
    }

    async fn process_passport_mint_log(
        &self,
        log: Log,
        contract_config: &ContractConfig,
        provider: &Provider<Ws>,
    ) -> Result<()> {
        // Extract values before consuming log
        let block_number = log.block_number.unwrap().as_u64();
        let tx_hash = format!("{:?}", log.transaction_hash.unwrap());

        // Parse as EAS Attested event
        if let Ok(event) = <AttestedEvent as EthLogDecode>::decode_log(&log.into()) {
            // Verify schema UID matches
            if let Some(expected_schema) = &contract_config.schema_uid {
                if event.schema_uid != *expected_schema {
                    return Ok(()); // Skip events with wrong schema
                }
            }

            let timestamp = self.get_timestamp_for_block(provider, block_number).await?;
            let datetime_timestamp = DateTime::from_timestamp(timestamp as i64, 0).unwrap();

            if let Err(err) = self
                .postgres_client
                .add_human_points_event(
                    &event.recipient.to_string().to_lowercase(),
                    "PMT",
                    datetime_timestamp,
                    &tx_hash,
                    Some(self.chain_id),
                )
                .await
            {
                eprintln!(
                    "Error - Failed to process passport mint event for chain {}: {:?}",
                    self.chain_id, err
                );
            }
        }

        Ok(())
    }

    async fn process_human_id_mint_log(&self, log: Log, provider: &Provider<Ws>) -> Result<()> {
        // Extract values before consuming log
        let block_number = log.block_number.unwrap().as_u64();
        let tx_hash = format!("{:?}", log.transaction_hash.unwrap());

        // Parse as Transfer event
        if let Ok(event) = <TransferEvent as EthLogDecode>::decode_log(&log.into()) {
            // Check if it's a mint (from address is zero)
            if event.from == Address::zero() {
                let timestamp = self.get_timestamp_for_block(provider, block_number).await?;
                let datetime_timestamp = DateTime::from_timestamp(timestamp as i64, 0).unwrap();

                if let Err(err) = self
                    .postgres_client
                    .add_human_points_event(
                        &event.to.to_string().to_lowercase(),
                        "HIM",
                        datetime_timestamp,
                        &tx_hash,
                        Some(self.chain_id),
                    )
                    .await
                {
                    eprintln!(
                        "Error - Failed to process Human ID mint event for chain {}: {:?}",
                        self.chain_id, err
                    );
                }
            }
        }

        Ok(())
    }

    async fn get_timestamp_for_block(
        &self,
        provider: &Provider<Ws>,
        block_number: u64,
    ) -> Result<i64> {
        if let Ok(Some(block)) = provider.get_block(block_number).await {
            return Ok(block.timestamp.as_u64() as i64);
        }
        Err(eyre::eyre!(
            "Failed to fetch block timestamp for block {}",
            block_number
        ))
    }

    // Staking event handlers
    async fn process_self_stake_event(
        &self,
        event: &SelfStakeFilter,
        meta: &LogMeta,
        provider: &Provider<Ws>,
    ) -> Result<()> {
        let block_number = meta.block_number.as_u64();
        let tx_hash = format!("{:?}", meta.transaction_hash);
        let timestamp = self.get_timestamp_for_block(provider, block_number).await? as u64;

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
                &tx_hash,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process self stake event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_community_stake_event(
        &self,
        event: &CommunityStakeFilter,
        meta: &LogMeta,
        provider: &Provider<Ws>,
    ) -> Result<()> {
        let block_number = meta.block_number.as_u64();
        let tx_hash = format!("{:?}", meta.transaction_hash);
        let timestamp = self.get_timestamp_for_block(provider, block_number).await? as u64;

        if let Err(err) = self
            .postgres_client
            .add_or_extend_stake(
                &StakeEventType::CommunityStake,
                self.chain_id,
                &event.staker,
                &event.stakee,
                &event.amount,
                &event.unlock_time,
                &timestamp,
                &block_number,
                &tx_hash,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process community stake event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_self_stake_withdrawn_event(
        &self,
        event: &SelfStakeWithdrawnFilter,
        meta: &LogMeta,
    ) -> Result<()> {
        let block_number = meta.block_number.as_u64();
        let tx_hash = format!("{:?}", meta.transaction_hash);

        if let Err(err) = self
            .postgres_client
            .update_stake_amount(
                &StakeEventType::SelfStakeWithdraw,
                self.chain_id,
                &event.staker,
                &event.staker,
                &event.amount,
                StakeAmountOperation::Subtract,
                &block_number,
                &tx_hash,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process self stake withdrawn event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_community_stake_withdrawn_event(
        &self,
        event: &CommunityStakeWithdrawnFilter,
        meta: &LogMeta,
    ) -> Result<()> {
        let block_number = meta.block_number.as_u64();
        let tx_hash = format!("{:?}", meta.transaction_hash);

        if let Err(err) = self
            .postgres_client
            .update_stake_amount(
                &StakeEventType::CommunityStakeWithdraw,
                self.chain_id,
                &event.staker,
                &event.stakee,
                &event.amount,
                StakeAmountOperation::Subtract,
                &block_number,
                &tx_hash,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process community stake withdrawn event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_slash_event(&self, event: &SlashFilter, meta: &LogMeta) -> Result<()> {
        let block_number = meta.block_number.as_u64();
        let tx_hash = format!("{:?}", meta.transaction_hash);

        if let Err(err) = self
            .postgres_client
            .update_stake_amount(
                &StakeEventType::Slash,
                self.chain_id,
                &event.staker,
                &event.staker,
                &event.amount,
                StakeAmountOperation::Subtract,
                &block_number,
                &tx_hash,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process slash event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_release_event(&self, event: &ReleaseFilter, meta: &LogMeta) -> Result<()> {
        let block_number = meta.block_number.as_u64();
        let tx_hash = format!("{:?}", meta.transaction_hash);

        if let Err(err) = self
            .postgres_client
            .update_stake_amount(
                &StakeEventType::Release,
                self.chain_id,
                &event.staker,
                &event.staker,
                &event.amount,
                StakeAmountOperation::Add,
                &block_number,
                &tx_hash,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process release event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }
}
