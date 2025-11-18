#!/bin/bash

# Script to stub out SQLX query macros for compilation without DATABASE_URL

echo "Stubbing SQLX queries in rust-scorer..."

# Backup original files first
for file in src/db/queries/*.rs; do
    if [ -f "$file" ]; then
        cp "$file" "$file.backup" 2>/dev/null || true
    fi
done

# Stub stamps.rs
cat > src/db/queries/stamps.rs << 'EOF'
use sqlx::PgPool;
use crate::db::errors::DatabaseError;
use crate::models::django::DjangoCeramicCache;

/// Get all ceramic cache entries for an address
pub async fn get_ceramic_cache_entries(
    _pool: &PgPool,
    _address: &str,
) -> Result<Vec<DjangoCeramicCache>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(vec![])
}

/// Get latest stamps per provider (deduplicated by updated_at)
pub async fn get_latest_stamps_by_provider(
    _pool: &PgPool,
    _address: &str,
) -> Result<Vec<DjangoCeramicCache>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(vec![])
}
EOF

# Stub utils.rs
cat > src/db/queries/utils.rs << 'EOF'
use sqlx::PgPool;
use crate::db::errors::DatabaseError;

/// Check if address is in allow list
pub async fn check_allow_list(
    _pool: &PgPool,
    _list_name: &str,
    _address: &str,
) -> Result<bool, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(false)
}

/// Get customization rule
pub async fn get_customization_rule(
    _pool: &PgPool,
    _provider_id: &str,
) -> Result<Option<serde_json::Value>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(None)
}
EOF

# Stub bans.rs
cat > src/db/queries/bans.rs << 'EOF'
use sqlx::PgPool;
use std::collections::HashSet;
use crate::db::errors::DatabaseError;

/// Check ADDRESS type bans
pub async fn check_address_bans(
    _pool: &PgPool,
    _addresses: &[String],
) -> Result<HashSet<String>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(HashSet::new())
}

/// Check HASH type bans
pub async fn check_hash_bans(
    _pool: &PgPool,
    _hashes: &[String],
) -> Result<HashSet<String>, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(HashSet::new())
}

/// Check PROVIDER type bans
pub async fn check_provider_bans(
    _pool: &PgPool,
    _provider: &str,
) -> Result<bool, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(false)
}
EOF

# Stub stakes.rs
cat > src/db/queries/stakes.rs << 'EOF'
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
EOF

# Stub cgrants.rs
cat > src/db/queries/cgrants.rs << 'EOF'
use sqlx::PgPool;
use crate::db::errors::DatabaseError;

/// Get contributor statistics across all grant contributions
pub async fn get_contributor_statistics(
    _pool: &PgPool,
    _address: &str,
) -> Result<serde_json::Value, DatabaseError> {
    // TODO: Implement after SQLX prepare
    Ok(serde_json::json!({
        "num_grants_contribute_to": 0,
        "num_rounds_contribute_to": 0,
        "total_contribution_amount": "0",
        "num_gr14_contributions": 0
    }))
}
EOF

echo "Stubbing complete. Original files backed up with .backup extension"