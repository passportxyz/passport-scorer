# Human Points Program - Django Implementation Spec

## Overview
Implement a points tracking system for the Human Points Program that rewards users for various Gitcoin Passport actions.

## Database Models

### 1. Update Community Model
Add field to `account.Community`:
```python
human_points_program = models.BooleanField(default=False, help_text="Include this community in the Human Points Program stats.")
```

### 2. Create HumanPointProgramStats Model
New model in `registry` app:
```python
class HumanPointProgramStats(models.Model):
    address = models.CharField(max_length=100, primary_key=True, db_index=True)
    passing_scores = models.IntegerField(default=0)
```

### 3. Create HumanPoints Model
New model in `registry` app:
```python
class HumanPoints(models.Model):
    address = models.CharField(max_length=100, db_index=True)
    action = models.CharField(max_length=50)
    points = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    tx_hash = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        # Unique constraints handled via migrations (see below)
        indexes = [
            models.Index(fields=['address', 'action']),
            models.Index(fields=['timestamp']),
        ]
```

### 4. Create Multiplier Model
```python
class HumanPointsMultiplier(models.Model):
    address = models.CharField(max_length=100, primary_key=True)
    multiplier = models.IntegerField(default=2)
```

## Migrations
Create unique constraints in migration:
```python
# Unique constraint for binary actions (stamps, staking)
migrations.RunSQL(
    "CREATE UNIQUE INDEX idx_binary_actions ON registry_humanpoints(address, action) "
    "WHERE action IN ('human_keys', 'identity_staking_bronze', 'identity_staking_silver', "
    "'identity_staking_gold', 'community_staking_beginner', 'community_staking_experienced', "
    "'community_staking_trusted');"
)

# Unique constraint for mint actions (with tx_hash)
migrations.RunSQL(
    "CREATE UNIQUE INDEX idx_mint_actions ON registry_humanpoints(address, action, tx_hash) "
    "WHERE action IN ('passport_mint', 'holonym_mint');"
)
```

## Implementation Points

### 1. Centralized Scoring Integration (atasks.py)
All points logic should be implemented in the scoring flow (likely in `registry/atasks.py`):

When a passport is scored:
1. **Update Community Stats**: If score >= 20 and community has `human_points_program=True`:
   - Increment HumanPointProgramStats.passing_scores
   - If passing_scores reaches 3, add 500 points to HumanPoints

2. **Process Binary Stamps**: 
   - Get multiplier once for the address
   - Iterate through valid stamps in the passport
   - For stamps that provide binary scores, award points:
     - Human Keys: 100 points
     - Identity Staking Bronze: 100 points
     - Identity Staking Silver: 200 points
     - Identity Staking Gold: 500 points
     - Community Staking Beginner: 100 points
     - Community Staking Experienced: 200 points
     - Community Staking Trusted: 500 points
   - Apply multiplier and insert into HumanPoints (unique constraint prevents duplicates)

### 2. Implementation Notes
- Only award points for valid stamps (check stamp validity/expiration)
- Fetch multiplier once per scoring operation, not per stamp
- Use bulk operations where possible to minimize database queries
- Leverage unique constraints to handle deduplication

### 3. API Response Updates
Modify ceramic-cache endpoints to include points data:
```python
{
    "stamps": [...],
    "score": {...},
    "points_data": {
        "total_points": 1800,
        "is_eligible": true,  # True if passing_scores >= 1
        "multiplier": 2
    }
}
```

### 4. Historical Data Population
One-time script to populate HumanPointsMultiplier:
- Query historical data for returning users
- Bulk insert addresses with multiplier=2

## Action Types (for reference)
- `scoring_bonus` - Scored >20 in 3+ approved communities
- `human_keys` - Human Network credential created
- `holonym_mint` - Holonym SBT minted (Optimism only)
- `passport_mint` - Passport minted on any chain
- `identity_staking_bronze/silver/gold` - Identity staking levels
- `community_staking_beginner/experienced/trusted` - Community staking levels

## Notes
- Points are calculated in real-time when queried
- Multipliers are applied at insertion time
- Binary actions (stamps) use nullifier for deduplication
- Mint actions use tx_hash for deduplication
- All timestamps should be in UTC


## Temporary Nature
This implementation is temporary for the points program duration. Consider:
- Feature flag to enable/disable points tracking
- Easy way to stop tracking without breaking existing functionality
- Clean separation from core logic
