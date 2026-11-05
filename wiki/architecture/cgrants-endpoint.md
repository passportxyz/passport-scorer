# CGrants Contributor Statistics Endpoint

GET /internal/cgrants/contributor_statistics - Combines contributions from two sources.

## Request

- **address** (required): Ethereum address, must be valid, converted to lowercase
- Returns 400 Bad Request if invalid
- Returns 422 Unprocessable Entity if missing

## Response

```json
{
  "num_grants_contribute_to": <float>,
  "total_contribution_amount": <float>
}
```

All values returned as floats, rounded to 2 decimal places. Returns zeros for addresses with no history.

## Query Logic

Combines two sources, summing results:

### CGrants Contributions

Data source: GrantContributionIndex table

- Filter by contributor_address and contribution.success = true
- Count distinct grant_id values
- Sum amount field (DecimalField, 18 decimals)
- NULL sums default to 0

### Protocol Contributions

Data sources: ProtocolContributions, SquelchedAccounts, RoundMapping tables

3-step process:

1. Get squelched rounds: Query SquelchedAccounts where address matches
2. Map to ETH addresses: Query RoundMapping for squelched round_numbers
3. Get contributions:
   - Filter where contributor = address AND amount >= 0.95
   - Exclude squelched rounds
   - Count distinct project values
   - Sum amount fields, rounded to 3 decimal places

Key points:
- Amount threshold >= 0.95 (depegged stablecoins)
- Count is distinct by project
- Squelched addresses return 0 for those rounds

### Combining Results

Add values from both sources, convert to float, round to 2 decimals.

## Database Tables

### GrantContributionIndex
- profile_id (FK)
- contribution_id (FK, nullable)
- grant_id (FK)
- round_num (nullable)
- amount (DecimalField, 18 decimals, 64 max_digits)
- contributor_address (indexed, nullable)

### Contribution
- subscription_id (FK)
- success (BooleanField)
- amount_per_period_usdt (DecimalField, 18 decimals)
- data (JSONField)

### ProtocolContributions
- ext_id (unique, indexed)
- contributor (indexed)
- round (indexed)
- project (indexed)
- amount (indexed)
- data (JSONField)

### SquelchedAccounts
- address (indexed)
- score_when_squelched
- sybil_signal
- round_number

### RoundMapping
- round_number
- round_eth_address (indexed)
- Unique constraint: (round_number, round_eth_address)

## Edge Cases

- No contributions: Return zeros
- Below threshold: Ignored in protocol stats
- Squelched addresses: Excluded from those rounds
- Failed contributions: Ignored in cgrants stats
- NULL sums: Default to 0
- Invalid address: 400 Bad Request
- Missing address: 422 Unprocessable Entity
