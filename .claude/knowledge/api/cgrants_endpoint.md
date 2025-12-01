# CGrants Contributor Statistics Endpoint

## Endpoint Overview

**Endpoint Path**: `/internal/cgrants/contributor_statistics` (Internal API)
**HTTP Method**: GET
**Authentication**: `internal_api_key` (Bearer token in Authorization header)
**Route Name**: `cgrants_contributor_statistics`

## Request Parameters

- **address** (required, query parameter): Ethereum address to get contributor statistics for
  - Must be a valid Ethereum address (validated via `is_valid_address()`)
  - Converted to lowercase before processing
  - Returns 400 Bad Request if invalid
  - Returns 422 Unprocessable Entity if missing

## Response Structure

Returns a JSON object with 2 fields (always present, even for zero contributions):

```json
{
  "num_grants_contribute_to": <float>,
  "total_contribution_amount": <float>
}
```

All numeric values are returned as floats (not integers), rounded to 2 decimal places.

## Query Logic

The endpoint combines data from TWO separate data sources:

### 1. CGrants Contributions (_get_contributor_statistics_for_cgrants)

**Data Source**: GrantContributionIndex table
**Query Logic**:
- Filter by `contributor_address = address` AND `contribution.success = true` (FK join required)
- If no contributions found, return early with `{"num_grants_contribute_to": 0, "total_contribution_amount": 0}`
- Count distinct grant_id values (number of grants the user contributed to)
- Sum all amount fields (total contribution amount in USD)
- Returns dict with keys: `num_grants_contribute_to`, `total_contribution_amount`

**Key Points**:
- Only counts SUCCESSFUL contributions (contribution.success must be true)
- Sums the "amount" field from GrantContributionIndex (decimal with 18 places, max 64 digits)
- If sum is NULL (no rows after filtering), defaults to 0
- Uses `.distinct()` on grant_id values to ensure accurate count

### 2. Protocol Contributions (_get_contributor_statistics_for_protocol)

**Data Sources**: ProtocolContributions, SquelchedAccounts, RoundMapping tables
**Query Logic** (3-step process):

1. **Get squelched rounds**:
   - Query SquelchedAccounts where `address = address`
   - Extract list of `round_number` values

2. **Map round numbers to Ethereum addresses**:
   - Query RoundMapping where `round_number IN (squelched_round_ids)`
   - Extract list of `round_eth_address` values

3. **Get contributions excluding squelched rounds**:
   - Filter ProtocolContributions where:
     - `contributor = address` (case-sensitive ETH address comparison)
     - `amount >= 0.95` (minimum threshold to filter out depegged/low-value contributions)
   - Exclude rows where `round IN (squelched_round_ids)`
   - Count distinct `project` values (number of grants/projects)
   - Sum all `amount` fields (total contribution in USD)
   - Rounds result to 3 decimal places
   - Returns dict with keys: `num_grants_contribute_to`, `total_contribution_amount`

**Key Points**:
- Amount threshold is >= 0.95 (not 1.0) to account for depegged stablecoins
- Count is distinct by project, not by contribution
- Sum is rounded to 3 decimal places (not 2)
- Squelched/sybil addresses return 0 contributions for those rounds
- NULL sums default to 0

### 3. Combining Results

The final response combines both sources:
- For each key present in either source, add the values together
- Convert to float and round to 2 decimal places
- Result is a dict with keys: `num_grants_contribute_to`, `total_contribution_amount`

## Database Tables Involved

### GrantContributionIndex
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `profile_id` (FK to Profile)
  - `contribution_id` (FK to Contribution, nullable)
  - `grant_id` (FK to Grant)
  - `round_num` (IntegerField, nullable)
  - `amount` (DecimalField, 18 decimals, 64 max_digits)
  - `contributor_address` (EthAddressField, max_length=100, indexed, nullable)
- **Indexes**: contributor_address, contribution_id, profile_id
- **Purpose**: Fast lookup for contributor statistics

### Contribution
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `subscription_id` (FK to Subscription)
  - `success` (BooleanField, default=False)
  - `amount_per_period_usdt` (DecimalField, 18 decimals)
  - `data` (JSONField)
- **Join**: GrantContributionIndex.contribution_id → Contribution.id

### ProtocolContributions
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `ext_id` (CharField, max_length=66, unique, indexed)
  - `contributor` (EthAddressField, max_length=100, indexed) - the contributor's address
  - `round` (EthAddressField, max_length=100, indexed) - the round's Ethereum address
  - `project` (EthAddressField, max_length=100, indexed) - the project's address
  - `amount` (DecimalField, 18 decimals, 64 max_digits, indexed)
  - `data` (JSONField)
- **Indexes**: ext_id (unique), contributor, round, project, amount
- **Purpose**: Store Allo protocol contributions from indexer

### SquelchedAccounts
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `address` (EthAddressField, max_length=100, indexed)
  - `score_when_squelched` (DecimalField, 18 decimals)
  - `sybil_signal` (BooleanField)
  - `round_number` (CharField, max_length=100)
- **Index**: address
- **Purpose**: Track sybil/flagged addresses per round (GG18+)

### RoundMapping
- **Primary Key**: id (BigAutoField)
- **Fields**:
  - `round_number` (CharField, max_length=100)
  - `round_eth_address` (EthAddressField, max_length=100, indexed)
- **Unique Constraint**: (round_number, round_eth_address)
- **Purpose**: Map GG round numbers to Ethereum addresses

## Edge Cases and Special Handling

1. **No contributions**: Returns `{"num_grants_contribute_to": 0.0, "total_contribution_amount": 0.0}`
2. **Contributions below threshold** (< 0.95 USD): Ignored in protocol contributions, excluded from count
3. **Squelched addresses**: Contributions in those rounds are excluded from protocol stats
4. **Failed contributions**: Ignored in cgrants stats (contribution.success=false)
5. **NULL sums**: Converted to 0 (both queries handle this)
6. **Address case sensitivity**: Converted to lowercase before querying
7. **Invalid address**: Raises InvalidAddressException (400 Bad Request)
8. **Missing address**: Returns 422 Unprocessable Entity (Django Ninja validation)

## Response Schema

PydanticSchema `ContributorStatistics`:
```
- num_grants_contribute_to: int (Field, but returned as float)
- total_contribution_amount: int (Field, but returned as float)
```

Note: Schema declares int type but Python code converts to float before returning JsonResponse.

## Reference Implementation Files

- **Main handler**: `/workspace/project/api/cgrants/api.py::handle_get_contributor_statistics()`
- **CGrants logic**: `/workspace/project/api/cgrants/api.py::_get_contributor_statistics_for_cgrants()`
- **Protocol logic**: `/workspace/project/api/cgrants/api.py::_get_contributor_statistics_for_protocol()`
- **Route registration**: `/workspace/project/api/internal/api.py::cgrants_contributor_statistics()`
- **Models**: `/workspace/project/api/cgrants/models.py`
- **Tests**: `/workspace/project/api/cgrants/test/test_cgrants_combined_contributions_api.py`

## Test Coverage

Tests verify:
- Combined contributions from both sources
- Zero contributions for addresses with no history
- Invalid address handling (400 response)
- Invalid token handling (401 response)
- Missing address parameter (422 response)
- Contributions below threshold are excluded
- Only protocol contributions count correctly
- Depegged stablecoin handling (0.99897 rounded to 1.0)
- Squelched profiles excluded from protocol stats
- Squelched in one round but not another (mixed case)

See: `/workspace/project/api/cgrants/api.py`, `/workspace/project/api/cgrants/models.py`, `/workspace/project/api/internal/api.py`
