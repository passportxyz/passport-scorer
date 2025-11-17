use rust_decimal::Decimal;
use sqlx::PgPool;
use serde::{Deserialize, Serialize};
use super::DomainError;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContributorStatistics {
    pub num_grants_contribute_to: i32,
    pub num_rounds_contribute_to: i32,
    pub total_contribution_amount: Decimal,
    pub num_gr14_contributions: i32,
}

/// Get contributor statistics for an address
/// Combines cgrants and protocol contributions
#[tracing::instrument(skip(pool))]
pub async fn get_contributor_statistics(
    address: &str,
    pool: &PgPool,
) -> Result<ContributorStatistics, DomainError> {
    // TODO: Implement contributor statistics logic
    // This needs to:
    // 1. Check if address is squelched
    // 2. Query cgrants_grantcontributionindex for grant contributions
    // 3. Query cgrants_protocolcontributions for protocol contributions
    // 4. Combine and return results

    // For now, return zeros
    Ok(ContributorStatistics {
        num_grants_contribute_to: 0,
        num_rounds_contribute_to: 0,
        total_contribution_amount: Decimal::from(0),
        num_gr14_contributions: 0,
    })
}

/// Check if an address is squelched (affects contribution statistics)
async fn is_address_squelched(
    address: &str,
    pool: &PgPool,
) -> Result<bool, DomainError> {
    // TODO: Query cgrants_squelchedaccounts table
    Ok(false)
}