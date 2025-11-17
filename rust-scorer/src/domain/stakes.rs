use rust_decimal::Decimal;
use sqlx::PgPool;
use serde::{Deserialize, Serialize};
use super::DomainError;

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct StakeSchema {
    pub chain: String,
    pub staker: String,
    pub stakee: String,
    pub amount: Decimal,
    pub lock_time: chrono::DateTime<chrono::Utc>,
    pub unlock_time: chrono::DateTime<chrono::Utc>,
    pub last_updated_in_block: i64,
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
    // TODO: Implement stake query logic
    // Query stake_stake table WHERE staker = $1 OR stakee = $1

    Ok(StakeResponse {
        items: vec![],
    })
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct GtcStakeEvent {
    pub id: i64,
    pub address: String,
    pub amount: Decimal,
    pub staked: bool,
    pub staker: String,
    pub event_type: String,
    pub round_id: i32,
    pub tx_hash: String,
    pub block_number: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GtcEventsResponse {
    pub results: Vec<GtcStakeEvent>,
}

/// Get legacy GTC stake events for an address and round
#[tracing::instrument(skip(pool))]
pub async fn get_legacy_gtc_events(
    address: &str,
    round_id: i32,
    pool: &PgPool,
) -> Result<GtcEventsResponse, DomainError> {
    // TODO: Implement legacy GTC stake event query
    // Query registry_gtcstakeevent table

    Ok(GtcEventsResponse {
        results: vec![],
    })
}