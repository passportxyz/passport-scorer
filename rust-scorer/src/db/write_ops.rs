use chrono::{DateTime, Utc};
use serde_json::Value as JsonValue;
use sqlx::{Transaction, Postgres, Row};
use std::collections::HashMap;
use tracing::{info, debug, warn};

use crate::db::errors::{DatabaseError, Result};
use crate::models::django::DjangoScoreFields;
use crate::models::internal::{ValidStamp, StampInfo};

/// Upsert a passport record
pub async fn upsert_passport(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i32,
) -> Result<i32> {
    debug!("Upserting passport for address: {} and community: {}", address, community_id);
    
    let row = sqlx::query(
        r#"
        INSERT INTO registry_passport (address, community_id, created_at, updated_at)
        VALUES (LOWER($1), $2, NOW(), NOW())
        ON CONFLICT (address, community_id)
        DO UPDATE SET updated_at = NOW()
        RETURNING id
        "#
    )
    .bind(address)
    .bind(community_id)
    .fetch_one(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let passport_id: i32 = row.get("id");
    
    info!("Upserted passport with ID: {}", passport_id);
    Ok(passport_id)
}

/// Delete all existing stamps for a passport
pub async fn delete_stamps(
    tx: &mut Transaction<'_, Postgres>,
    passport_id: i32,
) -> Result<u64> {
    debug!("Deleting existing stamps for passport_id: {}", passport_id);
    
    let result = sqlx::query(
        "DELETE FROM registry_stamp WHERE passport_id = $1"
    )
    .bind(passport_id)
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let deleted = result.rows_affected();
    info!("Deleted {} existing stamps", deleted);
    Ok(deleted)
}

/// Bulk insert stamps
pub async fn bulk_insert_stamps(
    tx: &mut Transaction<'_, Postgres>,
    passport_id: i32,
    stamps: &[ValidStamp],
) -> Result<u64> {
    if stamps.is_empty() {
        info!("No stamps to insert");
        return Ok(0);
    }
    
    debug!("Bulk inserting {} stamps for passport_id: {}", stamps.len(), passport_id);
    
    let providers: Vec<String> = stamps.iter().map(|s| s.provider.clone()).collect();
    let credentials: Vec<JsonValue> = stamps.iter().map(|s| s.credential.clone()).collect();
    let passport_ids: Vec<i32> = vec![passport_id; stamps.len()];
    
    let result = sqlx::query(
        r#"
        INSERT INTO registry_stamp (passport_id, provider, credential, created_at, updated_at)
        SELECT * FROM UNNEST($1::int[], $2::text[], $3::jsonb[]) 
        AS t(passport_id, provider, credential), 
        (SELECT NOW() as created_at, NOW() as updated_at) AS times
        "#
    )
    .bind(&passport_ids[..])
    .bind(&providers[..])
    .bind(&credentials[..])
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let inserted = result.rows_affected();
    info!("Inserted {} stamps", inserted);
    Ok(inserted)
}

/// Upsert a score record
pub async fn upsert_score(
    tx: &mut Transaction<'_, Postgres>,
    passport_id: i32,
    score_fields: &DjangoScoreFields,
) -> Result<i32> {
    debug!("Upserting score for passport_id: {}", passport_id);
    
    let row = sqlx::query(
        r#"
        INSERT INTO registry_score (
            passport_id, 
            score, 
            status, 
            last_score_timestamp,
            evidence, 
            stamps, 
            stamp_scores, 
            expiration_date,
            error,
            created_at,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
        ON CONFLICT (passport_id)
        DO UPDATE SET
            score = EXCLUDED.score,
            status = EXCLUDED.status,
            last_score_timestamp = EXCLUDED.last_score_timestamp,
            evidence = EXCLUDED.evidence,
            stamps = EXCLUDED.stamps,
            stamp_scores = EXCLUDED.stamp_scores,
            expiration_date = EXCLUDED.expiration_date,
            error = EXCLUDED.error,
            updated_at = NOW()
        RETURNING id
        "#
    )
    .bind(passport_id)
    .bind(score_fields.score)
    .bind(&score_fields.status)
    .bind(score_fields.last_score_timestamp)
    .bind(&score_fields.evidence)
    .bind(serde_json::to_value(&score_fields.stamps).unwrap())
    .bind(&score_fields.stamp_scores)
    .bind(score_fields.expiration_date)
    .bind(&score_fields.error)
    .fetch_one(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let score_id: i32 = row.get("id");
    
    info!("Upserted score with ID: {} (score: {})", score_id, score_fields.score);
    Ok(score_id)
}

/// Bulk upsert hash scorer links with retry logic for LIFO deduplication
pub async fn bulk_upsert_hash_links(
    tx: &mut Transaction<'_, Postgres>,
    links_to_create: Vec<(String, String, i32, DateTime<Utc>)>, // (hash, address, community_id, expires_at)
    links_to_update: Vec<(String, String, i32, DateTime<Utc>)>,
) -> Result<()> {
    debug!("Upserting {} new and {} existing hash links", 
        links_to_create.len(), links_to_update.len());
    
    // Bulk insert new links
    if !links_to_create.is_empty() {
        let hashes: Vec<String> = links_to_create.iter().map(|l| l.0.clone()).collect();
        let addresses: Vec<String> = links_to_create.iter().map(|l| l.1.clone()).collect();
        let community_ids: Vec<i32> = links_to_create.iter().map(|l| l.2).collect();
        let expires_ats: Vec<DateTime<Utc>> = links_to_create.iter().map(|l| l.3).collect();
        
        sqlx::query(
            r#"
            INSERT INTO registry_hashscorerlink (hash, address, community_id, expires_at)
            SELECT * FROM UNNEST($1::text[], $2::text[], $3::int[], $4::timestamptz[])
            AS t(hash, address, community_id, expires_at)
            "#
        )
        .bind(&hashes[..])
        .bind(&addresses[..])
        .bind(&community_ids[..])
        .bind(&expires_ats[..])
        .execute(&mut **tx)
        .await
        .map_err(|e| {
            // Check if it's an integrity error (concurrent insert)
            if let Some(db_error) = e.as_database_error() {
                if db_error.code().as_deref() == Some("23505") { // unique_violation
                    return DatabaseError::IntegrityError(
                        "Concurrent hash link insertion detected".to_string()
                    );
                }
            }
            DatabaseError::QueryError(e)
        })?;
        
        info!("Inserted {} new hash links", links_to_create.len());
    }
    
    // Update existing links (expired or owned)
    for (hash, address, community_id, expires_at) in &links_to_update {
        sqlx::query(
            r#"
            UPDATE registry_hashscorerlink
            SET address = $1, expires_at = $2
            WHERE hash = $3 AND community_id = $4
            "#
        )
        .bind(address)
        .bind(expires_at)
        .bind(hash)
        .bind(community_id)
        .execute(&mut **tx)
        .await
        .map_err(|e| DatabaseError::QueryError(e))?;
    }
    
    if !links_to_update.is_empty() {
        info!("Updated {} existing hash links", links_to_update.len());
    }
    
    Ok(())
}

/// Verify expected number of hash links were created
pub async fn verify_hash_links(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i32,
    expected_nullifiers: &[String],
) -> Result<bool> {
    debug!("Verifying hash links for {} expected nullifiers", expected_nullifiers.len());
    
    let row = sqlx::query(
        r#"
        SELECT COUNT(*) as count
        FROM registry_hashscorerlink
        WHERE LOWER(address) = LOWER($1)
            AND community_id = $2
            AND hash = ANY($3)
        "#
    )
    .bind(address)
    .bind(community_id)
    .bind(expected_nullifiers)
    .fetch_one(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let count: i64 = row.get("count");
    let expected = expected_nullifiers.len() as i64;
    
    if count != expected {
        warn!("Hash link count mismatch: expected {}, found {}", expected, count);
        return Ok(false);
    }
    
    info!("Hash link verification successful: {} links", count);
    Ok(true)
}

/// Insert LIFO deduplication events
pub async fn insert_dedup_events(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i32,
    clashing_stamps: &HashMap<String, StampInfo>,
) -> Result<u64> {
    if clashing_stamps.is_empty() {
        return Ok(0);
    }
    
    debug!("Inserting {} LIFO deduplication events", clashing_stamps.len());
    
    let mut actions = Vec::new();
    let mut addresses = Vec::new();
    let mut data_values = Vec::new();
    let mut community_ids = Vec::new();
    
    for (provider, stamp_info) in clashing_stamps {
        actions.push("LIFO_DEDUPLICATION".to_string());
        addresses.push(address.to_string());
        data_values.push(serde_json::json!({
            "nullifiers": stamp_info.nullifiers,
            "provider": provider,
            "community_id": community_id,
        }));
        community_ids.push(community_id);
    }
    
    let result = sqlx::query(
        r#"
        INSERT INTO registry_event (action, address, data, community_id, created_at)
        SELECT * FROM UNNEST($1::text[], $2::text[], $3::jsonb[], $4::int[])
        AS t(action, address, data, community_id),
        (SELECT NOW() as created_at) AS times
        "#
    )
    .bind(&actions[..])
    .bind(&addresses[..])
    .bind(&data_values[..])
    .bind(&community_ids[..])
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let inserted = result.rows_affected();
    info!("Inserted {} deduplication events", inserted);
    Ok(inserted)
}

/// Insert score update event
pub async fn insert_score_update_event(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i32,
    score_id: i32,
    passport_id: i32,
    score_fields: &DjangoScoreFields,
) -> Result<()> {
    debug!("Inserting SCORE_UPDATE event for score_id: {}", score_id);
    
    // Match Django's serializers.serialize() format
    let event_data = serde_json::json!([{
        "model": "registry.score",
        "pk": score_id,
        "fields": {
            "passport": passport_id,
            "score": score_fields.score.to_string(),
            "last_score_timestamp": score_fields.last_score_timestamp.to_rfc3339(),
            "status": score_fields.status,
            "error": score_fields.error,
            "evidence": score_fields.evidence,
            "stamp_scores": score_fields.stamp_scores,
            "stamps": score_fields.stamps,
            "expiration_date": score_fields.expiration_date.map(|d| d.to_rfc3339())
        }
    }]);
    
    sqlx::query(
        r#"
        INSERT INTO registry_event (action, address, data, community_id, created_at)
        VALUES ('SCORE_UPDATE', $1, $2, $3, NOW())
        "#
    )
    .bind(address)
    .bind(event_data)
    .bind(community_id)
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    info!("Inserted SCORE_UPDATE event");
    Ok(())
}

/// Record passing score for Human Points
pub async fn record_passing_score(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i32,
) -> Result<()> {
    debug!("Recording passing score for Human Points");
    
    sqlx::query(
        r#"
        INSERT INTO registry_humanpointscommunityqualifiedusers (address, community_id, created_at)
        VALUES (LOWER($1), $2, NOW())
        ON CONFLICT (address, community_id) DO NOTHING
        "#
    )
    .bind(address)
    .bind(community_id)
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    info!("Recorded passing score for Human Points");
    Ok(())
}

/// Record stamp actions for Human Points
pub async fn record_stamp_actions(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    stamps: &[ValidStamp],
) -> Result<u64> {
    if stamps.is_empty() {
        return Ok(0);
    }
    
    debug!("Recording {} stamp actions for Human Points", stamps.len());
    
    // Map providers to Human Points actions
    let human_key_providers = vec!["Google", "Twitter", "Discord", "GitHub"]; // Example providers
    
    let mut addresses = Vec::new();
    let mut actions = Vec::new();
    let mut providers = Vec::new();
    let mut nullifiers = Vec::new();
    
    for stamp in stamps {
        if human_key_providers.contains(&stamp.provider.as_str()) {
            addresses.push(address.to_string());
            actions.push("HUMAN_KEYS".to_string());
            providers.push(stamp.provider.clone());
            // Use first nullifier as tx_hash for Human Keys
            nullifiers.push(stamp.nullifiers.first().cloned().unwrap_or_default());
        }
    }
    
    if addresses.is_empty() {
        return Ok(0);
    }
    
    let result = sqlx::query(
        r#"
        INSERT INTO registry_humanpoints (address, action, provider, tx_hash, created_at)
        SELECT * FROM UNNEST($1::text[], $2::text[], $3::text[], $4::text[])
        AS t(address, action, provider, tx_hash),
        (SELECT NOW() as created_at) AS times
        ON CONFLICT (address, action, provider) 
        DO UPDATE SET tx_hash = EXCLUDED.tx_hash, updated_at = NOW()
        "#
    )
    .bind(&addresses[..])
    .bind(&actions[..])
    .bind(&providers[..])
    .bind(&nullifiers[..])
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let inserted = result.rows_affected();
    info!("Recorded {} stamp actions for Human Points", inserted);
    Ok(inserted)
}

/// Award scoring bonus for Human Points (4+ passing communities)
pub async fn award_scoring_bonus(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
) -> Result<bool> {
    debug!("Checking and awarding scoring bonus");
    
    let result = sqlx::query(
        r#"
        WITH qualified AS (
            SELECT COUNT(DISTINCT community_id) as count
            FROM registry_humanpointscommunityqualifiedusers
            WHERE LOWER(address) = LOWER($1)
        )
        INSERT INTO registry_humanpoints (address, action, created_at)
        SELECT $1, 'SCORING_BONUS', NOW()
        FROM qualified
        WHERE count >= 4
        ON CONFLICT (address, action, chain_id, provider, tx_hash) DO NOTHING
        "#
    )
    .bind(address)
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let inserted = result.rows_affected();
    
    if inserted > 0 {
        info!("Awarded scoring bonus for Human Points");
        Ok(true)
    } else {
        Ok(false)
    }
}

/// Award MetaMask OG bonus if eligible (limit 5000)
pub async fn award_metamask_og_bonus(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    has_metamask_stamp: bool,
) -> Result<bool> {
    if !has_metamask_stamp {
        return Ok(false);
    }
    
    debug!("Checking and awarding MetaMask OG bonus");
    
    // Check if under 5000 limit
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
    
    let current_count: i64 = row.get("count");
    
    if current_count >= 5000 {
        info!("MetaMask OG bonus limit reached (5000)");
        return Ok(false);
    }
    
    let result = sqlx::query(
        r#"
        INSERT INTO registry_humanpoints (address, action, created_at)
        VALUES (LOWER($1), 'METAMASK_OG', NOW())
        ON CONFLICT (address, action, chain_id, provider, tx_hash) DO NOTHING
        "#
    )
    .bind(address)
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;
    
    let inserted = result.rows_affected();
    
    if inserted > 0 {
        info!("Awarded MetaMask OG bonus");
        Ok(true)
    } else {
        Ok(false)
    }
}

#[cfg(test)]
mod tests {
    
    
    // Integration tests will be added when we have a test database setup
}