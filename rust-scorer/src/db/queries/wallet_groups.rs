use sqlx::{PgPool, Postgres, Transaction};

use crate::db::DatabaseError;

/// Get wallet group info for an address: (group_id, all member addresses).
/// Returns None if address is not in any group.
pub async fn get_wallet_group(
    pool: &PgPool,
    address: &str,
) -> Result<Option<(i64, Vec<String>)>, DatabaseError> {
    let rows: Vec<(i64, String)> = sqlx::query_as(
        r#"
        SELECT m1.group_id, m2.address
        FROM account_walletgroupmembership m1
        JOIN account_walletgroupmembership m2 ON m1.group_id = m2.group_id
        WHERE m1.address = $1
        "#,
    )
    .bind(address)
    .fetch_all(pool)
    .await?;

    if rows.is_empty() {
        return Ok(None);
    }

    let group_id = rows[0].0;
    let addresses: Vec<String> = rows.into_iter().map(|(_, a)| a).collect();
    Ok(Some((group_id, addresses)))
}

/// Get the canonical address for a group+community. Returns None if no claim exists.
pub async fn get_canonical_claim(
    pool: &PgPool,
    group_id: i64,
    community_id: i64,
) -> Result<Option<String>, DatabaseError> {
    let row: Option<(String,)> = sqlx::query_as(
        r#"
        SELECT canonical_address
        FROM account_walletgroupcommunityclaim
        WHERE group_id = $1 AND community_id = $2
        "#,
    )
    .bind(group_id)
    .bind(community_id)
    .fetch_optional(pool)
    .await?;

    Ok(row.map(|(a,)| a))
}

/// Create a canonical claim, returning the actual canonical address.
/// Uses ON CONFLICT DO NOTHING to handle races - if another wallet won,
/// we read back the existing claim.
pub async fn upsert_canonical_claim(
    tx: &mut Transaction<'_, Postgres>,
    group_id: i64,
    community_id: i64,
    address: &str,
) -> Result<String, DatabaseError> {
    // Try to insert; if another wallet already claimed, this is a no-op
    sqlx::query(
        r#"
        INSERT INTO account_walletgroupcommunityclaim (group_id, community_id, canonical_address, claimed_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (group_id, community_id) DO NOTHING
        "#,
    )
    .bind(group_id)
    .bind(community_id)
    .bind(address)
    .execute(&mut **tx)
    .await?;

    // Read back the actual canonical address (may be ours or the race winner's)
    let (canonical,): (String,) = sqlx::query_as(
        r#"
        SELECT canonical_address
        FROM account_walletgroupcommunityclaim
        WHERE group_id = $1 AND community_id = $2
        "#,
    )
    .bind(group_id)
    .bind(community_id)
    .fetch_one(&mut **tx)
    .await?;

    Ok(canonical)
}

/// Delete a canonical claim (used when the score has expired).
pub async fn delete_canonical_claim(
    tx: &mut Transaction<'_, Postgres>,
    group_id: i64,
    community_id: i64,
) -> Result<(), DatabaseError> {
    sqlx::query(
        r#"
        DELETE FROM account_walletgroupcommunityclaim
        WHERE group_id = $1 AND community_id = $2
        "#,
    )
    .bind(group_id)
    .bind(community_id)
    .execute(&mut **tx)
    .await?;

    Ok(())
}
