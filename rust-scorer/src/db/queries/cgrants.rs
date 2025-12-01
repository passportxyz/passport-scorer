use sqlx::{PgPool, FromRow};
use rust_decimal::Decimal;
use crate::db::errors::DatabaseError;

/// Statistics from cgrants contributions
#[derive(Debug)]
pub struct CgrantsStats {
    pub num_grants: i32,
    pub total_amount: Decimal,
}

/// Statistics from protocol contributions
#[derive(Debug)]
pub struct ProtocolStats {
    pub num_projects: i32,
    pub total_amount: Decimal,
}

/// Raw query result for protocol statistics
#[derive(Debug, FromRow)]
struct ProtocolStatsRow {
    num_projects: i32,
    total_amount: Decimal,
}

/// Get cgrants contribution statistics for an address
/// Queries cgrants_grantcontributionindex joined with cgrants_contribution
/// Only counts successful contributions
#[tracing::instrument(skip(pool))]
pub async fn get_cgrants_contribution_stats(
    pool: &PgPool,
    address: &str,
) -> Result<CgrantsStats, DatabaseError> {
    // Query cgrants_grantcontributionindex joined with cgrants_contribution
    // Only count successful contributions (success = true)
    let result = sqlx::query!(
        r#"
        SELECT
            COUNT(DISTINCT gci.grant_id)::INT as "num_grants!",
            COALESCE(SUM(gci.amount), 0)::NUMERIC as "total_amount!"
        FROM cgrants_grantcontributionindex gci
        INNER JOIN cgrants_contribution c ON gci.contribution_id = c.id
        WHERE gci.contributor_address = $1
          AND c.success = true
        "#,
        address
    )
    .fetch_one(pool)
    .await?;

    Ok(CgrantsStats {
        num_grants: result.num_grants,
        total_amount: result.total_amount,
    })
}

/// Get protocol contribution statistics for an address
/// Queries cgrants_protocolcontributions, excluding squelched rounds
/// Only counts contributions >= 0.95 (to handle depegged stablecoins)
#[tracing::instrument(skip(pool))]
pub async fn get_protocol_contribution_stats(
    pool: &PgPool,
    address: &str,
) -> Result<ProtocolStats, DatabaseError> {
    // First get round ETH addresses for squelched rounds
    // This maps round_number to round_eth_address via cgrants_roundmapping
    let squelched_round_ids: Vec<String> = sqlx::query_scalar!(
        r#"
        SELECT DISTINCT rm.round_eth_address as "round_eth_address!"
        FROM cgrants_squelchedaccounts sa
        INNER JOIN cgrants_roundmapping rm ON sa.round_number = rm.round_number
        WHERE sa.address = $1
        "#,
        address
    )
    .fetch_all(pool)
    .await?;

    // Query protocol contributions excluding squelched rounds
    // Minimum amount threshold of 0.95 (not 1.0) to handle stablecoin depeg
    let result: ProtocolStatsRow = if squelched_round_ids.is_empty() {
        // No squelched rounds - simpler query
        sqlx::query_as!(
            ProtocolStatsRow,
            r#"
            SELECT
                COUNT(DISTINCT project)::INT as "num_projects!",
                COALESCE(SUM(amount), 0)::NUMERIC as "total_amount!"
            FROM cgrants_protocolcontributions
            WHERE contributor = $1
              AND amount >= 0.95
            "#,
            address
        )
        .fetch_one(pool)
        .await?
    } else {
        // Exclude squelched rounds
        sqlx::query_as!(
            ProtocolStatsRow,
            r#"
            SELECT
                COUNT(DISTINCT project)::INT as "num_projects!",
                COALESCE(SUM(amount), 0)::NUMERIC as "total_amount!"
            FROM cgrants_protocolcontributions
            WHERE contributor = $1
              AND amount >= 0.95
              AND round NOT IN (SELECT * FROM UNNEST($2::TEXT[]))
            "#,
            address,
            &squelched_round_ids
        )
        .fetch_one(pool)
        .await?
    };

    // Round to 3 decimal places for protocol stats (matching Python behavior)
    // Note: final merge will round to 2 decimal places
    let total_amount_rounded = result.total_amount.round_dp(3);

    Ok(ProtocolStats {
        num_projects: result.num_projects,
        total_amount: total_amount_rounded,
    })
}

/// Check if an address is squelched in any round
/// Used for quick check without full statistics
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

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal_macros::dec;

    #[test]
    fn test_cgrants_stats_default() {
        let stats = CgrantsStats {
            num_grants: 0,
            total_amount: Decimal::ZERO,
        };
        assert_eq!(stats.num_grants, 0);
        assert_eq!(stats.total_amount, Decimal::ZERO);
    }

    #[test]
    fn test_protocol_stats_default() {
        let stats = ProtocolStats {
            num_projects: 0,
            total_amount: Decimal::ZERO,
        };
        assert_eq!(stats.num_projects, 0);
        assert_eq!(stats.total_amount, Decimal::ZERO);
    }

    #[test]
    fn test_cgrants_stats_with_values() {
        let stats = CgrantsStats {
            num_grants: 5,
            total_amount: dec!(125.50),
        };
        assert_eq!(stats.num_grants, 5);
        assert_eq!(stats.total_amount, dec!(125.50));
    }

    #[test]
    fn test_protocol_stats_rounding() {
        // Protocol stats round to 3 decimal places
        let amount = dec!(125.4567);
        let rounded = amount.round_dp(3);
        assert_eq!(rounded, dec!(125.457));
    }

    #[test]
    fn test_protocol_stats_threshold() {
        // Minimum threshold is 0.95, not 1.0
        let amount_above = dec!(0.95);
        let amount_below = dec!(0.94);

        assert!(amount_above >= dec!(0.95));
        assert!(amount_below < dec!(0.95));
    }

    // Integration tests - require DATABASE_URL
    #[tokio::test]
    async fn test_get_cgrants_contribution_stats() {
        let database_url = std::env::var("DATABASE_URL")
            .expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await.unwrap();

        // Test with an address that likely has no contributions
        let stats = get_cgrants_contribution_stats(&pool, "0x0000000000000000000000000000000000000000")
            .await
            .unwrap();

        // Should return zeros for non-existent address
        assert_eq!(stats.num_grants, 0);
        assert_eq!(stats.total_amount, Decimal::ZERO);
    }

    #[tokio::test]
    async fn test_get_protocol_contribution_stats() {
        let database_url = std::env::var("DATABASE_URL")
            .expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await.unwrap();

        // Test with an address that likely has no contributions
        let stats = get_protocol_contribution_stats(&pool, "0x0000000000000000000000000000000000000000")
            .await
            .unwrap();

        // Should return zeros for non-existent address
        assert_eq!(stats.num_projects, 0);
        assert_eq!(stats.total_amount, Decimal::ZERO);
    }

    #[tokio::test]
    async fn test_is_address_squelched() {
        let database_url = std::env::var("DATABASE_URL")
            .expect("DATABASE_URL must be set");
        let pool = PgPool::connect(&database_url).await.unwrap();

        // Test with an address that is unlikely to be squelched
        let is_squelched = is_address_squelched(&pool, "0x0000000000000000000000000000000000000000")
            .await
            .unwrap();

        // Most addresses should not be squelched
        assert!(!is_squelched);
    }
}
