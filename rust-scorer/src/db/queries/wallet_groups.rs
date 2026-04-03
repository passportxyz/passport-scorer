use sqlx::PgPool;

use crate::db::DatabaseError;

/// Get all addresses in the same wallet group as the given address.
/// Returns empty vec if address is not in any group.
pub async fn get_wallet_group_addresses(
    pool: &PgPool,
    address: &str,
) -> Result<Vec<String>, DatabaseError> {
    let rows: Vec<(String,)> = sqlx::query_as(
        r#"
        SELECT m2.address
        FROM account_walletgroupmembership m1
        JOIN account_walletgroupmembership m2 ON m1.group_id = m2.group_id
        WHERE m1.address = $1
        "#,
    )
    .bind(address)
    .fetch_all(pool)
    .await?;

    Ok(rows.into_iter().map(|(a,)| a).collect())
}

/// Get the group_id for a given address. Returns None if not in a group.
pub async fn get_group_id_for_address(
    pool: &PgPool,
    address: &str,
) -> Result<Option<i32>, DatabaseError> {
    let row: Option<(i32,)> = sqlx::query_as(
        r#"
        SELECT group_id
        FROM account_walletgroupmembership
        WHERE address = $1
        "#,
    )
    .bind(address)
    .fetch_optional(pool)
    .await?;

    Ok(row.map(|(id,)| id))
}

/// Get the canonical address for a group+community. Returns None if no claim exists.
pub async fn get_canonical_claim(
    pool: &PgPool,
    group_id: i32,
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
    pool: &PgPool,
    group_id: i32,
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
    .execute(pool)
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
    .fetch_one(pool)
    .await?;

    Ok(canonical)
}

/// Delete a canonical claim (used when the score has expired).
pub async fn delete_canonical_claim(
    pool: &PgPool,
    group_id: i32,
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
    .execute(pool)
    .await?;

    Ok(())
}
