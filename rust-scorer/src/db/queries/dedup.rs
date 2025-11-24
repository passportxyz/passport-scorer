use chrono::{DateTime, Utc};
use sqlx::{Transaction, Postgres, Row};
use std::collections::HashMap;
use tracing::{info, debug, warn};

use crate::db::errors::{DatabaseError, Result};
use crate::models::django::DjangoHashScorerLink;
use crate::models::internal::StampInfo;

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

/// Bulk upsert hash scorer links with retry logic for LIFO deduplication
#[tracing::instrument(skip(tx, links_to_create, links_to_update), fields(
    new_links = links_to_create.len(),
    update_links = links_to_update.len()
))]
pub async fn bulk_upsert_hash_links(
    tx: &mut Transaction<'_, Postgres>,
    links_to_create: Vec<(String, String, i64, DateTime<Utc>)>, // (hash, address, community_id, expires_at)
    links_to_update: Vec<(String, String, i64, DateTime<Utc>)>,
) -> Result<()> {
    debug!("Upserting {} new and {} existing hash links",
        links_to_create.len(), links_to_update.len());

    // Bulk insert new links
    if !links_to_create.is_empty() {
        let hashes: Vec<String> = links_to_create.iter().map(|l| l.0.clone()).collect();
        let addresses: Vec<String> = links_to_create.iter().map(|l| l.1.clone()).collect();
        let community_ids: Vec<i64> = links_to_create.iter().map(|l| l.2).collect();
        let expires_ats: Vec<DateTime<Utc>> = links_to_create.iter().map(|l| l.3).collect();

        sqlx::query(
            r#"
            INSERT INTO registry_hashscorerlink (hash, address, community_id, expires_at)
            SELECT * FROM UNNEST($1::text[], $2::text[], $3::bigint[], $4::timestamptz[])
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
#[tracing::instrument(skip(tx, expected_nullifiers), fields(
    address = %address,
    community_id = community_id,
    expected_count = expected_nullifiers.len()
))]
pub async fn verify_hash_links(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i64,
    expected_nullifiers: &[String],
) -> Result<bool> {
    debug!("Verifying hash links for {} expected nullifiers", expected_nullifiers.len());

    let row = sqlx::query(
        r#"
        SELECT COUNT(*) as count
        FROM registry_hashscorerlink
        WHERE address = LOWER($1)
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
#[tracing::instrument(skip(tx, clashing_stamps), fields(
    address = %address,
    community_id = community_id,
    event_count = clashing_stamps.len()
))]
pub async fn insert_dedup_events(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i64,
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
        actions.push("LDP".to_string());
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
        SELECT * FROM UNNEST($1::text[], $2::text[], $3::jsonb[], $4::bigint[])
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

/// Insert SCORE_UPDATE event after score persistence
#[tracing::instrument(skip(tx, event_data), fields(address = address, community_id = community_id))]
pub async fn insert_score_update_event(
    tx: &mut Transaction<'_, Postgres>,
    address: &str,
    community_id: i64,
    event_data: serde_json::Value,
) -> Result<u64> {
    debug!("Inserting SCORE_UPDATE event");

    let result = sqlx::query(
        r#"
        INSERT INTO registry_event (action, address, data, community_id, created_at)
        VALUES ('SCU', $1, $2, $3, NOW())
        "#
    )
    .bind(address)
    .bind(event_data)
    .bind(community_id)
    .execute(&mut **tx)
    .await
    .map_err(|e| DatabaseError::QueryError(e))?;

    let inserted = result.rows_affected();
    info!("Inserted SCORE_UPDATE event");
    Ok(inserted)
}
