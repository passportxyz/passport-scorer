// Internal API handlers - no authentication required (internal ALB only)
// These are thin handlers that orchestrate HTTP concerns and call domain logic

use axum::{
    extract::{Path, Query, State},
    Json,
};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use std::collections::HashMap;
use tracing::info;

use crate::api::error::{ApiError, ApiResult};
use crate::api::utils::is_valid_eth_address;
use crate::db::queries::bans::check_revocations;
use crate::domain;
use crate::models::v2_api::V2ScoreResponse;

/// Maximum number of items allowed in bulk operations
const MAX_BULK_CACHE_SIZE: usize = 100;

/// Credential subject containing hash, provider, and DID id
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CredentialSubject {
    pub hash: Option<String>,
    pub provider: Option<String>,
    pub id: Option<String>,
}

/// Credential wrapper for ban checking
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Credential {
    pub credential_subject: CredentialSubject,
}

/// Payload for revocation check
#[derive(Debug, Clone, Deserialize)]
pub struct RevocationCheckPayload {
    pub proof_values: Vec<String>,
}

/// Response for revocation check
#[derive(Debug, Clone, Serialize)]
pub struct RevocationCheckResponse {
    pub proof_value: String,
    pub is_revoked: bool,
}

/// Internal score handler - no authentication needed
#[tracing::instrument(
    skip(pool),
    fields(
        scorer_id = scorer_id,
        address = %address
    )
)]
pub async fn internal_score_handler(
    Path((scorer_id, address)): Path<(i64, String)>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<V2ScoreResponse>> {
    info!("Processing internal score request");

    // 1. Input validation
    let address = address.to_lowercase();
    if !is_valid_eth_address(&address) {
        return Err(ApiError::BadRequest("Invalid Ethereum address format".to_string()));
    }

    // 2. No authentication needed (internal ALB)

    // 3. Call shared domain logic (no human points for internal endpoint)
    Ok(Json(domain::calculate_score_for_address(
        &address,
        scorer_id,
        &pool,
    ).await?))
}

/// Internal weights handler
#[tracing::instrument(skip(pool))]
pub async fn internal_weights_handler(
    Query(params): Query<HashMap<String, String>>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<HashMap<String, f64>>> {
    info!("Processing internal weights request");

    // 1. Parse community_id from query params
    let scorer_id = params
        .get("community_id")
        .and_then(|s| s.parse::<i64>().ok());

    // 2. Call shared domain logic
    Ok(Json(domain::weights::get_scorer_weights(scorer_id, &pool).await?))
}

/// Internal ban check handler
#[tracing::instrument(skip(pool, credentials))]
pub async fn internal_check_bans_handler(
    State(pool): State<PgPool>,
    Json(credentials): Json<Vec<Credential>>,
) -> ApiResult<Json<Vec<domain::bans::BanCheckResult>>> {
    info!("Processing internal ban check request");

    // 1. Validate we have credentials
    if credentials.is_empty() {
        return Err(ApiError::BadRequest("Must provide valid credential(s)".to_string()));
    }

    // 2. Extract unique DIDs and validate all credentials are for same address
    let unique_ids: std::collections::HashSet<String> = credentials
        .iter()
        .filter_map(|c| c.credential_subject.id.clone())
        .collect();

    if unique_ids.is_empty() {
        return Err(ApiError::BadRequest("Must provide valid credential(s)".to_string()));
    }

    if unique_ids.len() > 1 {
        return Err(ApiError::BadRequest(
            "All credentials must be issued to the same address".to_string(),
        ));
    }

    // 3. Extract address from DID (format: did:pkh:eip155:1:0x...)
    let did = unique_ids.into_iter().next().unwrap();
    let address = did.split(':').last().unwrap_or(&did).to_string();

    // 4. Extract hashes and providers from credentials (in same order for result mapping)
    let credential_hashes: Vec<String> = credentials
        .iter()
        .map(|c| c.credential_subject.hash.clone().unwrap_or_default())
        .collect();

    let providers: Vec<String> = credentials
        .iter()
        .map(|c| c.credential_subject.provider.clone().unwrap_or_default())
        .collect();

    // 5. Call domain logic
    Ok(Json(domain::bans::check_credentials_for_bans(
        &address,
        &credential_hashes,
        &providers,
        &pool,
    )
    .await?))
}

/// Internal revocation check handler
#[tracing::instrument(skip(pool, payload))]
pub async fn internal_check_revocations_handler(
    State(pool): State<PgPool>,
    Json(payload): Json<RevocationCheckPayload>,
) -> ApiResult<Json<Vec<RevocationCheckResponse>>> {
    info!("Processing internal revocation check request");

    // 1. Validate payload size
    if payload.proof_values.len() > MAX_BULK_CACHE_SIZE {
        return Err(ApiError::BadRequest(format!(
            "Too many stamps. Maximum allowed is {}",
            MAX_BULK_CACHE_SIZE
        )));
    }

    // 2. Query for revocations
    let revoked_proof_values = check_revocations(&pool, &payload.proof_values)
        .await
        .map_err(|e| ApiError::Database(e.to_string()))?;

    // 3. Build response with is_revoked status for each proof value
    let revoked_set: std::collections::HashSet<String> = revoked_proof_values.into_iter().collect();

    let results: Vec<RevocationCheckResponse> = payload
        .proof_values
        .into_iter()
        .map(|proof_value| RevocationCheckResponse {
            is_revoked: revoked_set.contains(&proof_value),
            proof_value,
        })
        .collect();

    Ok(Json(results))
}

/// Internal allow list handler
#[tracing::instrument(skip(pool))]
pub async fn internal_allow_list_handler(
    Path((list, address)): Path<(String, String)>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::allow_list::AllowListResponse>> {
    info!("Processing internal allow list check");

    Ok(Json(domain::allow_list::check_allow_list_membership(&list, &address, &pool).await?))
}

/// Internal credential definition handler
#[tracing::instrument(skip(pool))]
pub async fn internal_credential_definition_handler(
    Path(provider_id): Path<String>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::allow_list::CredentialDefinitionResponse>> {
    info!("Processing internal credential definition request");

    // Axum's Path extractor already URL-decodes path parameters (e.g. %23 -> #)
    Ok(Json(domain::allow_list::get_credential_definition(&provider_id, &pool).await?))
}

/// Internal GTC stake handler
#[tracing::instrument(skip(pool))]
pub async fn internal_stake_gtc_handler(
    Path(address): Path<String>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::stakes::StakeResponse>> {
    info!("Processing internal GTC stake request");

    Ok(Json(domain::stakes::get_gtc_stakes(&address, &pool).await?))
}

/// Internal legacy GTC stake handler
#[tracing::instrument(skip(pool))]
pub async fn internal_legacy_stake_handler(
    Path((address, round_id)): Path<(String, i32)>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::stakes::GtcEventsResponse>> {
    info!("Processing internal legacy GTC stake request");

    Ok(Json(domain::stakes::get_legacy_gtc_events(&address, round_id, &pool).await?))
}

/// Internal cgrants contributor statistics handler
#[tracing::instrument(skip(pool))]
pub async fn internal_cgrants_statistics_handler(
    Query(params): Query<HashMap<String, String>>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<domain::cgrants::ContributorStatistics>> {
    info!("Processing internal cgrants statistics request");

    // Get address parameter (returns 422 if missing, matching Django Ninja behavior)
    let address = params.get("address")
        .ok_or_else(|| ApiError::BadRequest("Missing address parameter".to_string()))?;

    // Validate Ethereum address format (returns 400 for invalid address)
    if !is_valid_eth_address(address) {
        return Err(ApiError::BadRequest("Invalid address.".to_string()));
    }

    Ok(Json(domain::cgrants::get_contributor_statistics(address, &pool).await?))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_credential_deserialization() {
        let json = json!({
            "credentialSubject": {
                "hash": "v0.0.0:abc123",
                "provider": "TestProvider",
                "id": "did:pkh:eip155:1:0x1234567890abcdef1234567890abcdef12345678"
            }
        });

        let credential: Credential = serde_json::from_value(json).unwrap();
        assert_eq!(credential.credential_subject.hash, Some("v0.0.0:abc123".to_string()));
        assert_eq!(credential.credential_subject.provider, Some("TestProvider".to_string()));
        assert_eq!(
            credential.credential_subject.id,
            Some("did:pkh:eip155:1:0x1234567890abcdef1234567890abcdef12345678".to_string())
        );
    }

    #[test]
    fn test_credential_deserialization_with_nulls() {
        let json = json!({
            "credentialSubject": {
                "hash": null,
                "provider": null,
                "id": "did:pkh:eip155:1:0x1234567890abcdef1234567890abcdef12345678"
            }
        });

        let credential: Credential = serde_json::from_value(json).unwrap();
        assert_eq!(credential.credential_subject.hash, None);
        assert_eq!(credential.credential_subject.provider, None);
    }

    #[test]
    fn test_address_extraction_from_did() {
        // Test DID format: did:pkh:eip155:1:0x...
        let did = "did:pkh:eip155:1:0x1234567890abcdef1234567890abcdef12345678";
        let address = did.split(':').last().unwrap_or(did);
        assert_eq!(address, "0x1234567890abcdef1234567890abcdef12345678");
    }

    #[test]
    fn test_address_extraction_simple_did() {
        // Test simpler DID format
        let did = "did:ethr:0xabcdef";
        let address = did.split(':').last().unwrap_or(did);
        assert_eq!(address, "0xabcdef");
    }

    #[test]
    fn test_revocation_check_payload_deserialization() {
        let json = json!({
            "proof_values": ["proof1", "proof2", "proof3"]
        });

        let payload: RevocationCheckPayload = serde_json::from_value(json).unwrap();
        assert_eq!(payload.proof_values.len(), 3);
        assert_eq!(payload.proof_values[0], "proof1");
    }

    #[test]
    fn test_revocation_check_response_serialization() {
        let response = RevocationCheckResponse {
            proof_value: "proof123".to_string(),
            is_revoked: true,
        };

        let json = serde_json::to_value(&response).unwrap();
        assert_eq!(json["proof_value"], "proof123");
        assert_eq!(json["is_revoked"], true);
    }

    #[test]
    fn test_max_bulk_cache_size_constant() {
        assert_eq!(MAX_BULK_CACHE_SIZE, 100);
    }

    #[test]
    fn test_multiple_credentials_same_address() {
        let credentials = vec![
            json!({
                "credentialSubject": {
                    "hash": "hash1",
                    "provider": "Provider1",
                    "id": "did:pkh:eip155:1:0xabc"
                }
            }),
            json!({
                "credentialSubject": {
                    "hash": "hash2",
                    "provider": "Provider2",
                    "id": "did:pkh:eip155:1:0xabc"
                }
            }),
        ];

        let parsed: Vec<Credential> = credentials
            .into_iter()
            .map(|c| serde_json::from_value(c).unwrap())
            .collect();

        // Extract unique IDs
        let unique_ids: std::collections::HashSet<String> = parsed
            .iter()
            .filter_map(|c| c.credential_subject.id.clone())
            .collect();

        assert_eq!(unique_ids.len(), 1);
    }

    #[test]
    fn test_multiple_credentials_different_addresses() {
        let credentials = vec![
            json!({
                "credentialSubject": {
                    "hash": "hash1",
                    "provider": "Provider1",
                    "id": "did:pkh:eip155:1:0xabc"
                }
            }),
            json!({
                "credentialSubject": {
                    "hash": "hash2",
                    "provider": "Provider2",
                    "id": "did:pkh:eip155:1:0xdef"
                }
            }),
        ];

        let parsed: Vec<Credential> = credentials
            .into_iter()
            .map(|c| serde_json::from_value(c).unwrap())
            .collect();

        // Extract unique IDs
        let unique_ids: std::collections::HashSet<String> = parsed
            .iter()
            .filter_map(|c| c.credential_subject.id.clone())
            .collect();

        // Should have 2 different addresses - this would trigger an error
        assert_eq!(unique_ids.len(), 2);
    }

    #[test]
    fn test_extract_hashes_and_providers() {
        let credentials = vec![
            json!({
                "credentialSubject": {
                    "hash": "hash1",
                    "provider": "Provider1",
                    "id": "did:pkh:eip155:1:0xabc"
                }
            }),
            json!({
                "credentialSubject": {
                    "hash": "hash2",
                    "provider": "Provider2",
                    "id": "did:pkh:eip155:1:0xabc"
                }
            }),
            json!({
                "credentialSubject": {
                    "hash": null,
                    "provider": null,
                    "id": "did:pkh:eip155:1:0xabc"
                }
            }),
        ];

        let parsed: Vec<Credential> = credentials
            .into_iter()
            .map(|c| serde_json::from_value(c).unwrap())
            .collect();

        let hashes: Vec<String> = parsed
            .iter()
            .map(|c| c.credential_subject.hash.clone().unwrap_or_default())
            .collect();

        let providers: Vec<String> = parsed
            .iter()
            .map(|c| c.credential_subject.provider.clone().unwrap_or_default())
            .collect();

        assert_eq!(hashes, vec!["hash1", "hash2", ""]);
        assert_eq!(providers, vec!["Provider1", "Provider2", ""]);
    }
}