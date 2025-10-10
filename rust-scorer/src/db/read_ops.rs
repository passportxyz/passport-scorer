use sqlx::{PgPool, Transaction, Postgres, Row};
use tracing::{info, debug};

use crate::db::errors::{DatabaseError, Result};
use crate::models::django::{
    DjangoCeramicCache, DjangoCommunity, DjangoBinaryWeightedScorer,
    DjangoApiKey, DjangoHashScorerLink, DjangoCustomization
};

/// Load credentials from ceramic_cache for an address
#[tracing::instrument(skip(pool), fields(address = %address))]
pub async fn load_ceramic_cache(
    pool: &PgPool,
    address: &str,
) -> Result<Vec<DjangoCeramicCache>> {
    debug!("Loading ceramic cache for address: {}", address);
    
    let records = sqlx::query_as::<_, DjangoCeramicCache>(
        r#"
        SELECT 
            id,
            address,
            provider,
            stamp,
            proof_value,
            deleted_at,
            created_at,
            updated_at
        FROM ceramic_cache_ceramiccache
        WHERE address = LOWER($1)
            AND deleted_at IS NULL
        ORDER BY provider, updated_at DESC
        "#
    )
    .bind(address)
    .fetch_all(pool)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    info!("Loaded {} ceramic cache records for address {}", records.len(), address);
    Ok(records)
}

/// Get the latest stamp per provider from ceramic cache
#[tracing::instrument(skip(pool), fields(address = %address))]
pub async fn get_latest_stamps_per_provider(
    pool: &PgPool,
    address: &str,
) -> Result<Vec<DjangoCeramicCache>> {
    debug!("Getting latest stamps per provider for address: {}", address);
    
    let records = sqlx::query_as::<_, DjangoCeramicCache>(
        r#"
        SELECT DISTINCT ON (provider)
            id,
            address,
            provider,
            stamp,
            proof_value,
            deleted_at,
            created_at,
            updated_at
        FROM ceramic_cache_ceramiccache
        WHERE address = LOWER($1)
            AND deleted_at IS NULL
        ORDER BY provider, updated_at DESC
        "#
    )
    .bind(address)
    .fetch_all(pool)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    info!("Found {} unique providers for address {}", records.len(), address);
    Ok(records)
}

/// Load binary weighted scorer configuration
#[tracing::instrument(skip(pool), fields(scorer_id = scorer_id))]
pub async fn load_scorer_config(
    pool: &PgPool,
    scorer_id: i64,
) -> Result<DjangoBinaryWeightedScorer> {
    debug!("Loading scorer config for scorer_id: {}", scorer_id);
    
    // Try BinaryWeightedScorer first, then fall back to WeightedScorer
    let scorer = match sqlx::query_as::<_, DjangoBinaryWeightedScorer>(
        r#"
        SELECT
            scorer_ptr_id,
            weights,
            threshold
        FROM scorer_weighted_binaryweightedscorer
        WHERE scorer_ptr_id = $1
        "#
    )
    .bind(scorer_id)
    .fetch_one(pool)
    .await
    {
        Ok(scorer) => scorer,
        Err(sqlx::Error::RowNotFound) => {
            // Try WeightedScorer table as fallback
            sqlx::query_as::<_, DjangoBinaryWeightedScorer>(
                r#"
                SELECT
                    scorer_ptr_id,
                    weights,
                    threshold
                FROM scorer_weighted_weightedscorer
                WHERE scorer_ptr_id = $1
                "#
            )
            .bind(scorer_id)
            .fetch_one(pool)
            .await
            .map_err(|e| match e {
                sqlx::Error::RowNotFound => DatabaseError::NotFound(
                    format!("Scorer configuration not found for scorer_id: {}", scorer_id)
                ),
                _ => DatabaseError::QueryError(e),
            })?
        }
        Err(e) => return Err(DatabaseError::QueryError(e)),
    };
    
    info!("Loaded scorer config with threshold: {}", scorer.threshold);
    Ok(scorer)
}

/// Load community settings
#[tracing::instrument(skip(pool), fields(community_id = community_id))]
pub async fn load_community(
    pool: &PgPool,
    community_id: i64,
) -> Result<DjangoCommunity> {
    debug!("Loading community settings for community_id: {}", community_id);
    
    let community = sqlx::query_as::<_, DjangoCommunity>(
        r#"
        SELECT
            id,
            name,
            description,
            human_points_program,
            created_at
        FROM account_community
        WHERE id = $1
        "#
    )
    .bind(community_id)
    .fetch_one(pool)
    .await
    .map_err(|e| match e {
        sqlx::Error::RowNotFound => DatabaseError::NotFound(
            format!("Community not found for id: {}", community_id)
        ),
        _ => DatabaseError::QueryError(e),
    })?;
    
    info!("Loaded community '{}' with human_points_program: {}", 
        community.name, community.human_points_program);
    Ok(community)
}

/// Validate API key and return key data
#[tracing::instrument(skip(pool, api_key_header))]
pub async fn validate_api_key(
    pool: &PgPool,
    api_key_header: &str,
) -> Result<DjangoApiKey> {
    debug!("Validating API key");
    
    // Extract prefix (first 8 chars) for lookup
    let prefix = if api_key_header.len() >= 8 {
        &api_key_header[..8]
    } else {
        api_key_header
    };
    
    // In real implementation, we'd hash the full key and compare
    // For now, we'll do a simplified lookup by prefix
    let api_key = sqlx::query_as::<_, DjangoApiKey>(
        r#"
        SELECT
            id,
            prefix,
            hashed_key,
            account_id,
            name,
            revoked,
            submit_passports,
            read_scores,
            create_scorers,
            created,
            expiry_date
        FROM account_accountapikey
        WHERE prefix = $1
            AND revoked = false
            AND (expiry_date IS NULL OR expiry_date > NOW())
        "#
    )
    .bind(prefix)
    .fetch_one(pool)
    .await
    .map_err(|e| match e {
        sqlx::Error::RowNotFound => DatabaseError::NotFound(
            "Invalid or expired API key".to_string()
        ),
        _ => DatabaseError::QueryError(e),
    })?;
    
    // Check read_scores permission
    if !api_key.read_scores {
        return Err(DatabaseError::InvalidData(
            "API key lacks read_scores permission".to_string()
        ));
    }
    
    info!("API key validated successfully");
    Ok(api_key)
}

/// Load existing hash scorer links for deduplication check
#[tracing::instrument(skip(tx), fields(community_id = community_id))]
pub async fn load_hash_scorer_links(
    tx: &mut Transaction<'_, Postgres>,
    community_id: i64,
    nullifiers: &[String],
) -> Result<Vec<DjangoHashScorerLink>> {
    debug!("Loading hash scorer links for {} nullifiers", nullifiers.len());
    
    let links = sqlx::query_as::<_, DjangoHashScorerLink>(
        r#"
        SELECT
            id,
            hash,
            address,
            community_id,
            expires_at
        FROM registry_hashscorerlink
        WHERE community_id = $1
            AND hash = ANY($2)
        "#
    )
    .bind(community_id)
    .bind(nullifiers)
    .fetch_all(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    info!("Found {} existing hash scorer links", links.len());
    Ok(links)
}

/// Check if customization exists for a community
#[tracing::instrument(skip(pool), fields(community_id = community_id))]
pub async fn load_customization(
    pool: &PgPool,
    community_id: i64,
) -> Result<Option<DjangoCustomization>> {
    debug!("Loading customization for community_id: {}", community_id);
    
    let customization = sqlx::query_as::<_, DjangoCustomization>(
        r#"
        SELECT
            id,
            scorer_id
        FROM account_customization
        WHERE scorer_id = $1
        "#
    )
    .bind(community_id)
    .fetch_optional(pool)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    if customization.is_some() {
        info!("Found customization for community {}", community_id);
    } else {
        info!("No customization found for community {}", community_id);
    }
    
    Ok(customization)
}

/// Load passport ID for an address and community
#[tracing::instrument(skip(tx), fields(address = %address, community_id = community_id))]
pub async fn get_passport_id(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i64,
) -> Result<Option<i64>> {
    debug!("Getting passport ID for address: {} and community: {}", address, community_id);
    
    let row = sqlx::query(
        r#"
        SELECT id
        FROM registry_passport
        WHERE address = LOWER($1)
            AND community_id = $2
        "#
    )
    .bind(address)
    .bind(community_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let passport_id = row.map(|r| r.get::<i64, _>("id"));
    
    if let Some(id) = passport_id {
        info!("Found existing passport with ID: {}", id);
    } else {
        info!("No existing passport found");
    }
    
    Ok(passport_id)
}

/// Count passing scores across communities for Human Points
#[tracing::instrument(skip(tx), fields(address = %address))]
pub async fn count_passing_scores(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
) -> Result<i64> {
    debug!("Counting passing scores for address: {}", address);
    
    let row = sqlx::query(
        r#"
        SELECT COUNT(DISTINCT community_id) as count
        FROM registry_humanpointscommunityqualifiedusers
        WHERE address = LOWER($1)
        "#
    )
    .bind(address)
    .fetch_one(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let count: i64 = row.get("count");
    
    info!("Address {} has {} passing scores across communities", address, count);
    Ok(count)
}

/// Check if MetaMask OG bonus has been awarded (limit 5000)
#[tracing::instrument(skip(tx))]
pub async fn count_metamask_og_awards(
    tx: &mut Transaction<'_, Postgres>,
) -> Result<i64> {
    debug!("Counting MetaMask OG awards");
    
    let row = sqlx::query(
        r#"
        SELECT COUNT(*) as count
        FROM registry_humanpoints
        WHERE action = 'METAMASK_OG'
        "#
    )
    .fetch_one(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let count: i64 = row.get("count");
    
    info!("Total MetaMask OG awards: {}", count);
    Ok(count)
}

#[cfg(test)]
mod tests {
    
    
    // Integration tests will be added when we have a test database setup
}
