use sqlx::PgPool;
use crate::db::errors::DatabaseError;

/// Check if a community exists
pub async fn check_community_exists(
    pool: &PgPool,
    scorer_id: i64,
) -> Result<bool, DatabaseError> {
    let result = sqlx::query!(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM account_community
            WHERE id = $1
        ) as "exists!"
        "#,
        scorer_id
    )
    .fetch_one(pool)
    .await?;

    Ok(result.exists)
}

/// Check if an address is in an allow list
pub async fn get_allow_list_membership(
    pool: &PgPool,
    list_name: &str,
    address: &str,
) -> Result<bool, DatabaseError> {
    let result = sqlx::query!(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM account_addresslistmember alm
            JOIN account_addresslist al ON alm.list_id = al.id
            WHERE al.name = $1 AND alm.address = $2
        ) as "exists!"
        "#,
        list_name,
        address
    )
    .fetch_one(pool)
    .await?;

    Ok(result.exists)
}

/// Get credential customization ruleset
pub async fn get_credential_ruleset(
    pool: &PgPool,
    provider_id: &str,
) -> Result<Option<serde_json::Value>, DatabaseError> {
    let result = sqlx::query!(
        r#"
        SELECT definition
        FROM account_customcredentialruleset
        WHERE provider_id = $1
        "#,
        provider_id
    )
    .fetch_optional(pool)
    .await?;

    Ok(result.map(|r| r.definition))
}