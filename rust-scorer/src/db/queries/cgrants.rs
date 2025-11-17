use sqlx::PgPool;
use rust_decimal::Decimal;
use crate::db::errors::DatabaseError;

/// Check if an address is squelched
pub async fn is_address_squelched(
    pool: &PgPool,
    address: &str,
) -> Result<bool, DatabaseError> {
    let result = sqlx::query!(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM cgrants_squelchedaccounts
            WHERE address = $1
        ) as "exists!"
        "#,
        address
    )
    .fetch_one(pool)
    .await?;

    Ok(result.exists)
}

#[derive(Debug)]
pub struct CgrantsStats {
    pub num_grants: i32,
    pub total_amount: Decimal,
}

/// Get cgrants contribution statistics
pub async fn get_cgrants_contribution_stats(
    pool: &PgPool,
    address: &str,
) -> Result<CgrantsStats, DatabaseError> {
    // TODO: Implement cgrants statistics queries
    // Query cgrants_grantcontributionindex joined with cgrants_contribution
    // WHERE contributor_address = $1 AND success = true
    Ok(CgrantsStats {
        num_grants: 0,
        total_amount: Decimal::from(0),
    })
}

#[derive(Debug)]
pub struct ProtocolStats {
    pub num_rounds: i32,
    pub total_amount: Decimal,
}

/// Get protocol contribution statistics
pub async fn get_protocol_contribution_stats(
    pool: &PgPool,
    address: &str,
) -> Result<ProtocolStats, DatabaseError> {
    // TODO: Implement protocol contribution queries
    // Query cgrants_protocolcontributions
    // WHERE contributor = $1
    Ok(ProtocolStats {
        num_rounds: 0,
        total_amount: Decimal::from(0),
    })
}

/// Get GR14 contribution count
pub async fn get_gr14_contributions(
    pool: &PgPool,
    address: &str,
    gr14_round_id: i32,
) -> Result<i32, DatabaseError> {
    // TODO: Implement GR14 specific query
    Ok(0)
}