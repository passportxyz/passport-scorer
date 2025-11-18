use sqlx::PgPool;
use rust_decimal::Decimal;
use crate::db::errors::DatabaseError;

#[derive(Debug)]
pub struct GtcStakeInfo {
    pub user_amount: Option<Decimal>,
    pub xdai_amount: Option<Decimal>,
    pub total: Decimal,
}

/// Get current GTC stake from gtcstaking_gtcstake table
pub async fn get_gtc_stake(
    _pool: &PgPool,
    _address: &str,
) -> Result<GtcStakeInfo, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(GtcStakeInfo {
        user_amount: None,
        xdai_amount: None,
        total: Decimal::ZERO,
    })
}

/// Get legacy GTC stake from event table for specific round
pub async fn get_legacy_gtc_stake(
    _pool: &PgPool,
    _address: &str,
    _round_id: i32,
) -> Result<Decimal, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(Decimal::ZERO)
}
