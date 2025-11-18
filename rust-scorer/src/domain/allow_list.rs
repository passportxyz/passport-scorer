use sqlx::PgPool;
use serde::{Deserialize, Serialize};
use super::DomainError;
use crate::db::queries::utils::{get_allow_list_membership, get_credential_ruleset};

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
    let is_member = get_allow_list_membership(pool, list_name, address)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?;

    Ok(AllowListResponse { is_member })
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
    // URL-decode provider_id (replace %23 with #)
    let decoded_provider = urlencoding::decode(provider_id)
        .map_err(|e| DomainError::Validation(format!("Invalid provider_id encoding: {}", e)))?;

    let ruleset = get_credential_ruleset(pool, &decoded_provider)
        .await
        .map_err(|e| DomainError::Database(e.to_string()))?
        .unwrap_or(serde_json::json!({}));

    Ok(CredentialDefinitionResponse { ruleset })
}