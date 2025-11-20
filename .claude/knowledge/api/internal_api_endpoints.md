# Internal API Endpoints

## Complete Inventory and Migration Status

### Already Implemented in Rust (3 endpoints)

1. **GET /internal/embed/validate-api-key** - validates partner API key
2. **POST /internal/embed/stamps/{address}** - adds stamps and rescores
3. **GET /internal/embed/score/{scorer_id}/{address}** - gets score with stamps

### Implemented in Phase 3 (9 endpoints)

1. **GET /internal/score/v2/{scorer_id}/{address}** - internal scoring without human points
2. **GET /internal/embed/weights** - retrieves scorer weights (NO AUTH REQUIRED!)
3. **POST /internal/check-bans** - checks credential bans
4. **POST /internal/check-revocations** - checks stamp revocations
5. **GET /internal/stake/gtc/{address}** - gets GTC stake amounts
6. **GET /internal/stake/legacy-gtc/{address}/{round_id}** - legacy GTC stake
7. **GET /internal/cgrants/contributor_statistics** - contributor stats
8. **GET /internal/allow-list/{list}/{address}** - checks allow list membership
9. **GET /internal/customization/credential/{provider_id}** - gets credential definition

## Authentication Notes

- Internal ALB endpoints don't require authentication (already inside VPC)
- Except /internal/embed/validate-api-key which validates the partner's API key
- Python uses CGRANTS_API_TOKEN from settings for internal_api_key auth
- Rust wouldn't need this since traffic is already authenticated at ALB level

## Database Queries

### 1. /internal/check-bans
```sql
SELECT * FROM ceramic_cache_ban
WHERE (address = %(address)s OR hash = ANY(%(hashes)s))
AND (end_time IS NULL OR end_time > NOW())
```

### 2. /internal/check-revocations
```sql
SELECT proof_value FROM ceramic_cache_revocation
WHERE proof_value = ANY(%(proof_values)s)
```

### 3. /internal/stake/gtc/{address}
```sql
SELECT id, chain, lock_time, unlock_time, last_updated_in_block,
       staker, stakee, current_amount
FROM stake_stake
WHERE staker = %(address)s OR stakee = %(address)s
```

### 4. /internal/stake/legacy-gtc/{address}/{round_id}
```sql
SELECT * FROM registry_gtcstakeevent
WHERE round_id = %(round_id)s
AND (staker = %(address)s OR address = %(address)s)
```

### 5. /internal/cgrants/contributor_statistics
Multiple queries - see separate detailed documentation in api/cgrants_endpoint.md

### 6. /internal/allow-list/{list}/{address}
```sql
SELECT EXISTS(
    SELECT 1 FROM account_addresslistmember alm
    JOIN account_addresslist al ON alm.list_id = al.id
    WHERE al.name = %(list_name)s AND alm.address = %(address)s
)
```

### 7. /internal/customization/credential/{provider_id}
```sql
SELECT definition FROM account_customcredentialruleset
WHERE provider_id = %(provider_id)s
```

### 8. /internal/embed/weights
No authentication, returns scorer weights from scorer_weighted_binaryweightedscorer or scorer_weighted_weightedscorer tables

### 9. /internal/score/v2/{scorer_id}/{address}
Reuses existing scoring logic without API key requirement

See: `api/internal/api.py`, `rust-scorer/src/api/server.rs`, `rust-scorer/src/api/embed.rs`
