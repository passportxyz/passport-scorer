use sqlx::PgPool;
use rust_decimal::Decimal;
use chrono::{DateTime, Utc};
use crate::db::errors::DatabaseError;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct Stake {
    pub id: i64,
    pub chain: i32,
    pub staker: String,
    pub stakee: String,
    pub current_amount: Decimal,
    pub lock_time: DateTime<Utc>,
    pub unlock_time: DateTime<Utc>,
    pub last_updated_in_block: Decimal,  // numeric(78,0)
}

/// Get stakes for an address (as staker or stakee)
pub async fn get_stakes_for_address(
    pool: &PgPool,
    address: &str,
) -> Result<Vec<Stake>, DatabaseError> {
    let stakes = sqlx::query_as!(
        Stake,
        r#"
        SELECT
            id,
            chain,
            staker,
            stakee,
            current_amount,
            lock_time,
            unlock_time,
            last_updated_in_block
        FROM stake_stake
        WHERE LOWER(staker) = LOWER($1) OR LOWER(stakee) = LOWER($1)
        "#,
        address
    )
    .fetch_all(pool)
    .await?;

    Ok(stakes)
}

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct GtcStakeEvent {
    pub id: i64,
    pub address: Option<String>,  // Nullable
    pub amount: Decimal,
    pub staked: bool,
    pub staker: String,
    pub event_type: String,
    pub round_id: i32,
    pub tx_hash: String,
    pub block_number: i32,
}

/// Get GTC stake events for address and round
pub async fn get_gtc_stake_events(
    pool: &PgPool,
    address: &str,
    round_id: i32,
) -> Result<Vec<GtcStakeEvent>, DatabaseError> {
    let events = sqlx::query_as!(
        GtcStakeEvent,
        r#"
        SELECT
            id,
            event_type,
            round_id,
            staker,
            address,
            amount,
            staked,
            block_number,
            tx_hash
        FROM registry_gtcstakeevent
        WHERE round_id = $1 AND (LOWER(staker) = LOWER($2) OR LOWER(address) = LOWER($2))
        "#,
        round_id,
        address
    )
    .fetch_all(pool)
    .await?;

    Ok(events)
}