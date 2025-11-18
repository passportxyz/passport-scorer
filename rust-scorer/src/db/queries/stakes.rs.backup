use sqlx::PgPool;
use rust_decimal::Decimal;
use crate::db::errors::DatabaseError;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct Stake {
    pub id: i64,
    pub chain: String,
    pub staker: String,
    pub stakee: String,
    pub current_amount: Decimal,
    pub lock_time: chrono::DateTime<chrono::Utc>,
    pub unlock_time: chrono::DateTime<chrono::Utc>,
    pub last_updated_in_block: i64,
}

/// Get stakes for an address (as staker or stakee)
pub async fn get_stakes_for_address(
    pool: &PgPool,
    address: &str,
) -> Result<Vec<Stake>, DatabaseError> {
    // TODO: Implement stake query
    // Query stake_stake table
    // WHERE staker = $1 OR stakee = $1
    Ok(vec![])
}

#[derive(Debug, Clone, sqlx::FromRow)]
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

/// Get GTC stake events for address and round
pub async fn get_gtc_stake_events(
    pool: &PgPool,
    address: &str,
    round_id: i32,
) -> Result<Vec<GtcStakeEvent>, DatabaseError> {
    // TODO: Implement GTC stake event query
    // Query registry_gtcstakeevent table
    // WHERE round_id = $1 AND (staker = $2 OR address = $2)
    Ok(vec![])
}