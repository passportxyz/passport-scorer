# Internal API Endpoints

12 endpoints for internal operations accessed from within VPC or private ALB.

## Complete Endpoint Inventory

1. **GET /internal/embed/validate-api-key** - Validates partner API key, returns rate limits
2. **POST /internal/embed/stamps/{address}** - Adds stamps and rescores passport
3. **GET /internal/embed/score/{scorer_id}/{address}** - Gets current score with stamps
4. **GET /internal/score/v2/{scorer_id}/{address}** - Internal scoring without API key auth
5. **GET /internal/embed/weights** - Returns scorer weights (NO AUTH REQUIRED)
6. **POST /internal/check-bans** - Checks credential bans
7. **POST /internal/check-revocations** - Checks stamp revocations
8. **GET /internal/stake/gtc/{address}** - Gets GTC staking records
9. **GET /internal/stake/legacy-gtc/{address}/{round_id}** - Legacy GTC stake events
10. **GET /internal/cgrants/contributor_statistics** - Combined contribution stats
11. **GET /internal/allow-list/{list}/{address}** - Checks allow list membership
12. **GET /internal/customization/credential/{provider_id}** - Gets custom credential definition

## Authentication

- Internal ALB endpoints require VPC access (no additional auth needed)
- /internal/embed/validate-api-key validates partner's API key
- /internal/embed/weights has NO authentication required
- Python uses internal_api_key from settings (CGRANTS_API_TOKEN)

## Core Database Queries

### Check Bans

```sql
SELECT * FROM ceramic_cache_ban
WHERE (address = %(address)s OR hash = ANY(%(hashes)s))
AND (end_time IS NULL OR end_time > NOW())
```

### Check Revocations

```sql
SELECT proof_value FROM ceramic_cache_revocation
WHERE proof_value = ANY(%(proof_values)s)
```

### GTC Stakes

```sql
SELECT id, chain, lock_time, unlock_time, last_updated_in_block,
       staker, stakee, current_amount
FROM stake_stake
WHERE staker = %(address)s OR stakee = %(address)s
```

### Legacy GTC Events

```sql
SELECT * FROM registry_gtcstakeevent
WHERE round_id = %(round_id)s
AND (staker = %(address)s OR address = %(address)s)
```

### Allow List Membership

```sql
SELECT EXISTS(
    SELECT 1 FROM account_addresslistmember alm
    JOIN account_addresslist al ON alm.list_id = al.id
    WHERE al.name = %(list_name)s AND alm.address = %(address)s
)
```

### Custom Credential Definition

```sql
SELECT definition FROM account_customcredentialruleset
WHERE provider_id = %(provider_id)s
```

## Contributor Statistics

See `wiki/architecture/cgrants-endpoint.md` for detailed implementation.

## Tables Involved

- ceramic_cache_ban: type, provider, hash, address, end_time
- ceramic_cache_revocation: proof_value
- stake_stake: staker, stakee, current_amount, chain
- registry_gtcstakeevent: staker, address (not stakee), round_id
- account_addresslist: name
- account_addresslistmember: address
- account_customcredentialruleset: provider_id, definition
- cgrants_grantcontributionindex: contributor_address, grant_id, amount
- cgrants_protocolcontributions: contributor, project, amount
- cgrants_squelchedaccounts: address
