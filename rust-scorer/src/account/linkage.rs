//! Linkage source for wallet grouping (Rust mirror of `api/account/linkage.py`).
//!
//! Phase 0 stub: solo set only. Phase 3b (#589) replaces with a Silk fetch +
//! SWR cache + `LINKED_WALLETS_SOURCE_ENABLED` killswitch +
//! `scorer.linked_wallets.fallback_to_solo` metric.

use sqlx::PgPool;

use crate::db::DatabaseError;

/// Return all addresses linked to `address`.
///
/// Phase 0 stub: returns just the solo address (lowercased). The `_pool`
/// argument is unused in the stub but kept so the signature matches what
/// Phase 3b needs (Silk HTTP call with DB-backed fallback metadata).
pub async fn get_linked_addresses(
    address: &str,
    _pool: &PgPool,
) -> Result<Vec<String>, DatabaseError> {
    Ok(vec![address.to_lowercase()])
}
