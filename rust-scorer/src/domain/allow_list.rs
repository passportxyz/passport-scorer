use sqlx::PgPool;
use serde::{Deserialize, Serialize};
use super::DomainError;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllowListResponse {
    pub is_member: bool,
}

/// Check if an address is a member of a specific allow list
#[tracing::instrument(skip(pool))]
pub async fn check_allow_list_membership(
    list_name: &str,
    address: &str,
    pool: &PgPool,
) -> Result<AllowListResponse, DomainError> {
    // TODO: Implement allow list check
    // Query account_addresslistmember joined with account_addresslist

    Ok(AllowListResponse {
        is_member: false,
    })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CredentialDefinitionResponse {
    pub ruleset: serde_json::Value,
}

/// Get credential customization definition for a provider
#[tracing::instrument(skip(pool))]
pub async fn get_credential_definition(
    provider_id: &str,
    pool: &PgPool,
) -> Result<CredentialDefinitionResponse, DomainError> {
    // TODO: Implement credential definition lookup
    // Query account_customcredentialruleset table
    // Note: Must URL-decode provider_id (replace %23 with #)

    Ok(CredentialDefinitionResponse {
        ruleset: serde_json::json!({}),
    })
}