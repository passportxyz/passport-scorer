use rust_decimal::prelude::ToPrimitive;
use sqlx::PgPool;
use serde::{Deserialize, Serialize};
use super::DomainError;
use crate::db::queries::cgrants;

/// Response structure matching Python's ContributorStatistics
/// Returns exactly 2 fields as floats with 2 decimal precision
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContributorStatistics {
    pub num_grants_contribute_to: f64,
    pub total_contribution_amount: f64,
}

/// Get contributor statistics for an address
/// Combines cgrants and protocol contributions, excluding squelched rounds
#[tracing::instrument(skip(pool))]
pub async fn get_contributor_statistics(
    address: &str,
    pool: &PgPool,
) -> Result<ContributorStatistics, DomainError> {
    // Normalize address to lowercase (matching Python behavior)
    let address = address.to_lowercase();

    // Get cgrants contribution statistics
    let cgrants_stats = cgrants::get_cgrants_contribution_stats(pool, &address).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // Get protocol contribution statistics (excludes squelched rounds)
    let protocol_stats = cgrants::get_protocol_contribution_stats(pool, &address).await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    // Combine statistics from both sources
    // CGrants: count distinct grant_id, sum amount
    // Protocol: count distinct project, sum amount (excluding squelched rounds)
    let total_grants = cgrants_stats.num_grants + protocol_stats.num_projects;
    let total_amount = cgrants_stats.total_amount + protocol_stats.total_amount;

    // Round to 2 decimal places and convert to f64 (matching Python behavior)
    let total_amount_rounded = total_amount
        .round_dp(2)
        .to_f64()
        .unwrap_or(0.0);

    Ok(ContributorStatistics {
        num_grants_contribute_to: total_grants as f64,
        total_contribution_amount: total_amount_rounded,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal_macros::dec;

    #[test]
    fn test_contributor_statistics_zero_values() {
        // Test that we can create stats with zero values
        let stats = ContributorStatistics {
            num_grants_contribute_to: 0.0,
            total_contribution_amount: 0.0,
        };
        assert_eq!(stats.num_grants_contribute_to, 0.0);
        assert_eq!(stats.total_contribution_amount, 0.0);
    }

    #[test]
    fn test_contributor_statistics_serialization() {
        // Test JSON serialization matches expected format
        let stats = ContributorStatistics {
            num_grants_contribute_to: 5.0,
            total_contribution_amount: 125.50,
        };

        let json = serde_json::to_string(&stats).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed["num_grants_contribute_to"], 5.0);
        assert_eq!(parsed["total_contribution_amount"], 125.5);
    }

    #[test]
    fn test_rounding_to_two_decimal_places() {
        // Test that amounts are properly rounded to 2 decimal places
        use rust_decimal::prelude::ToPrimitive;

        // Test value that needs rounding
        let amount = dec!(125.456789);
        let rounded = amount.round_dp(2).to_f64().unwrap_or(0.0);
        assert_eq!(rounded, 125.46);

        // Test value that doesn't need rounding
        let amount2 = dec!(100.00);
        let rounded2 = amount2.round_dp(2).to_f64().unwrap_or(0.0);
        assert_eq!(rounded2, 100.0);
    }

    #[test]
    fn test_contributor_statistics_with_large_values() {
        // Test handling of large values
        let stats = ContributorStatistics {
            num_grants_contribute_to: 10000.0,
            total_contribution_amount: 999999.99,
        };
        assert_eq!(stats.num_grants_contribute_to, 10000.0);
        assert_eq!(stats.total_contribution_amount, 999999.99);
    }

    #[test]
    fn test_combining_cgrants_and_protocol_stats() {
        // Simulating the combination logic
        let cgrants_grants = 5;
        let cgrants_amount = dec!(100.50);
        let protocol_projects = 3;
        let protocol_amount = dec!(50.25);

        let total_grants = cgrants_grants + protocol_projects;
        let total_amount = (cgrants_amount + protocol_amount).round_dp(2);

        assert_eq!(total_grants, 8);
        assert_eq!(total_amount, dec!(150.75));
    }
}
