use rust_decimal::Decimal;
use sqlx::PgPool;
use serde::{Deserialize, Serialize};
use super::DomainError;
use crate::db::queries::stakes::{get_stakes_for_address, get_gtc_stake_events};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StakeSchema {
    pub chain: i32,
    pub staker: String,
    pub stakee: String,
    pub amount: String,  // Serialize Decimal as string
    pub lock_time: String,
    pub unlock_time: String,
    pub last_updated_in_block: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StakeResponse {
    pub items: Vec<StakeSchema>,
}

/// Get GTC stakes for an address
#[tracing::instrument(skip(pool))]
pub async fn get_gtc_stakes(
    address: &str,
    pool: &PgPool,
) -> Result<StakeResponse, DomainError> {
    let stakes = get_stakes_for_address(pool, address)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    let items = stakes
        .into_iter()
        .map(|s| StakeSchema {
            chain: s.chain,
            staker: s.staker,
            stakee: s.stakee,
            amount: s.current_amount.to_string(),
            lock_time: s.lock_time.to_rfc3339(),
            unlock_time: s.unlock_time.to_rfc3339(),
            last_updated_in_block: s.last_updated_in_block.to_string(),
        })
        .collect();

    Ok(StakeResponse { items })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GtcStakeEventSchema {
    pub id: i64,
    pub address: Option<String>,
    pub amount: String,
    pub staked: bool,
    pub staker: String,
    pub event_type: String,
    pub round_id: i32,
    pub tx_hash: String,
    pub block_number: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GtcEventsResponse {
    pub results: Vec<GtcStakeEventSchema>,
}

/// Get legacy GTC stake events for an address and round
#[tracing::instrument(skip(pool))]
pub async fn get_legacy_gtc_events(
    address: &str,
    round_id: i32,
    pool: &PgPool,
) -> Result<GtcEventsResponse, DomainError> {
    let events = get_gtc_stake_events(pool, address, round_id)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    let results = events
        .into_iter()
        .map(|e| GtcStakeEventSchema {
            id: e.id,
            address: e.address,
            amount: e.amount.to_string(),
            staked: e.staked,
            staker: e.staker,
            event_type: e.event_type,
            round_id: e.round_id,
            tx_hash: e.tx_hash,
            block_number: e.block_number,
        })
        .collect();

    Ok(GtcEventsResponse { results })
}