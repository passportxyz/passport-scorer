# Human Points Program - Django Implementation Spec

## Overview
Implement a points tracking system for the Human Points Program that rewards users for various Gitcoin Passport actions.

## Progress Status
- ✅ Models created (HumanPointsCommunityQualifiedUsers, HumanPoints, HumanPointsMultiplier, HumanPointsConfig)
- ✅ Community model updated with human_points_program field
- ✅ Consolidated migration created with unique constraints (0049_humanpoints_models.py)
- ✅ Admin interfaces configured
- ✅ Comprehensive test suite created and passing:
  - test_human_points_models.py - Model functionality tests
  - test_human_points_scoring_integration.py - Async scoring integration tests
  - test_human_points_constraints.py - Database constraint tests
  - test_human_points_api_response.py - API response tests
- ✅ Scoring integration in atasks.py (implemented)
- ✅ API endpoint updates (V2 API returns points_data)
- ✅ Feature flag implementation (implemented - HUMAN_POINTS_ENABLED setting)
- ✅ Multiplier backfill management command (implemented - backfill_human_points_multipliers.py)
- ✅ Human Keys nullifier extraction verification (implemented - updated to extract from credentialSubject)

## Database Models

### 1. Update Community Model
Add field to `account.Community`:
```python
human_points_program = models.BooleanField(default=False, help_text="Include this community in the Human Points Program stats.")
```

### 2. Create HumanPointsCommunityQualifiedUsers Model
New model in `registry` app:
```python
class HumanPointsCommunityQualifiedUsers(models.Model):
    address = models.CharField(max_length=100, db_index=True)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="human_points_qualified_users",
    )
    
    class Meta:
        unique_together = [("address", "community")]
```

### 3. Create HumanPoints Model (Normalized)
New model in `registry` app - stores actions WITHOUT point values:
```python
class HumanPoints(models.Model):
    # Example usage:
    #   obj.action = HumanPoints.Action.PASSPORT_MINT
    class Action(models.TextChoices):
        SCORING_BONUS = "SCB"
        HUMAN_KEYS = "HKY"
        IDENTITY_STAKING_BRONZE = "ISB"
        IDENTITY_STAKING_SILVER = "ISS"
        IDENTITY_STAKING_GOLD = "ISG"
        COMMUNITY_STAKING_BEGINNER = "CSB"
        COMMUNITY_STAKING_EXPERIENCED = "CSE"
        COMMUNITY_STAKING_TRUSTED = "CST"
        PASSPORT_MINT = "PMT"
        HUMAN_ID_MINT = "HIM"

    address = models.CharField(max_length=100, db_index=True)
    action = models.CharField(max_length=3, choices=Action.choices, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    tx_hash = models.CharField(max_length=100, null=True, blank=True)
    chain_id = models.IntegerField(null=True, blank=True, db_index=True)  # Only set for mint actions (PMT, HIM)

    class Meta:
        # Unique constraints handled via migrations (see below)
        indexes = [
            models.Index(fields=['address', 'action']),
            models.Index(fields=['address', 'timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['chain_id', 'action']),
        ]
```

### 4. Create Multiplier Model
```python
class HumanPointsMultiplier(models.Model):
    address = models.CharField(max_length=100, primary_key=True)
    multiplier = models.IntegerField(default=2)
```

### 5. Create Points Configuration Model
```python
class HumanPointsConfig(models.Model):
    action = models.CharField(max_length=50, unique=True, db_index=True)
    points = models.IntegerField()
    active = models.BooleanField(default=True)
    effective_date = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['action', 'active']),
        ]
```

## Migrations
Consolidated migration (0049_humanpoints_models.py) creates unique constraints:
```python
# Unique constraint for binary actions (stamps, staking, scoring bonus)
migrations.RunSQL(
    "CREATE UNIQUE INDEX idx_binary_actions ON registry_humanpoints(address, action) "
    "WHERE action IN ('SCB', 'ISB', 'ISS', 'ISG', 'CSB', 'CSE', 'CST');"
)

# Unique constraint for actions that require tx_hash (mints and human keys)
# For mint actions (PMT, HIM), chain_id is also part of the unique constraint
migrations.RunSQL(
    "CREATE UNIQUE INDEX idx_tx_hash_actions ON registry_humanpoints(address, action, tx_hash, chain_id) "
    "WHERE action IN ('PMT', 'HIM', 'HKY');"
)
```

## Implementation Points

### 1. Centralized Scoring Integration (atasks.py)
All points logic should be implemented in the scoring flow (likely in `registry/atasks.py`):

When a passport is scored:
1. **Update Community Stats**: If score >= 20 and community has `human_points_program=True`:
   - Add/update HumanPointsCommunityQualifiedUsers entry for this address and community
   - Count how many approved communities this address has qualified for
   - If reaching 3 for the first time, add action 'SCB' (scoring_bonus) to HumanPoints

2. **Process Binary Stamps**:
   - Iterate through valid stamps in the passport
   - For stamps that provide binary scores, record the action in HumanPoints
   - For Human Keys stamp: Store the nullifier in the tx_hash field for deduplication
   - Actions are recorded WITHOUT point values (normalized approach)
   - Unique constraints prevent duplicates

### 2. Implementation Notes
- Only record actions for valid stamps (check stamp validity/expiration)
- Use bulk operations where possible to minimize database queries
- Leverage unique constraints to handle deduplication
- Point values are configured in HumanPointsConfig table, not hardcoded

### 3. Initial Point Configuration
Populate HumanPointsConfig table with:
```python
# One-time data migration or fixture
configs = [
    (HumanPoints.Action.SCORING_BONUS, 500),
    (HumanPoints.Action.HUMAN_KEYS, 100),
    (HumanPoints.Action.IDENTITY_STAKING_BRONZE, 100),
    (HumanPoints.Action.IDENTITY_STAKING_SILVER, 200),
    (HumanPoints.Action.IDENTITY_STAKING_GOLD, 500),
    (HumanPoints.Action.COMMUNITY_STAKING_BEGINNER, 100),
    (HumanPoints.Action.COMMUNITY_STAKING_EXPERIENCED, 200),
    (HumanPoints.Action.COMMUNITY_STAKING_TRUSTED, 500),
    (HumanPoints.Action.PASSPORT_MINT, 300),
    (HumanPoints.Action.HUMAN_ID_MINT, 1000),
]
for action, points in configs:
    HumanPointsConfig.objects.create(action=action, points=points)
```

### 4. API Response Updates
Modify ceramic-cache endpoints to include points data:
```python
{
    "stamps": [...],
    "score": {...},
    "points_data": {
        "total_points": 1800,
        "is_eligible": true,  # True if passing_scores >= 1
        "multiplier": 2,
        "breakdown": {
            "scoring_bonus": 500,
            "human_keys": 200,
            "passport_mint": 600,
            "staking": 500
        }
    }
}
```

**Note for UI Integration**: After an on-chain mint transaction succeeds, the UI should:
- Wait 3-5 seconds for blockchain finality
- Re-query the scoring endpoint to get updated points
- This ensures the indexer has processed the mint event

### 5. Query Optimization

#### Efficient Points Query
```python
# Django ORM query with proper joins
def get_user_points(address: str):
    actions = HumanPoints.objects.filter(address=address).select_related()
    multiplier = HumanPointsMultiplier.objects.filter(address=address).first()
    mult_value = multiplier.multiplier if multiplier else 1

    # Join with config to calculate points
    points_data = {}
    total = 0
    for action in actions:
        config = HumanPointsConfig.objects.get(action=action.action, active=True)
        points = config.points * mult_value
        points_data[action.action] = points
        total += points

    return {
        "total_points": total,
        "breakdown": points_data,
        "multiplier": mult_value
    }
```

#### On-Demand Database View for Analytics
```sql
-- This view is created once and queries execute against it in real-time
-- No materialization needed since the full table will only be queried a handful of times
CREATE OR REPLACE VIEW human_points_summary AS
SELECT
    hp.address,
    SUM(pc.points * COALESCE(hpm.multiplier, 1)) as total_points,
    json_object_agg(hp.action, pc.points * COALESCE(hpm.multiplier, 1)) as breakdown,
    COALESCE(hpm.multiplier, 1) as multiplier,
    COUNT(DISTINCT hp.action) as unique_actions,
    MAX(hp.timestamp) as last_action_time
FROM registry_humanpoints hp
JOIN registry_humanpointsconfig pc ON hp.action = pc.action AND pc.active = true
LEFT JOIN registry_humanpointsmultiplier hpm ON hp.address = hpm.address
GROUP BY hp.address, hpm.multiplier;
```


### 6. Historical Data Population
One-time script to populate HumanPointsMultiplier:
- Query historical data for returning users
- Bulk insert addresses with multiplier=2

## Action Types (for reference)
- `scoring_bonus` - Scored >20 in 3+ approved communities
- `human_keys` - Human Network credential created
- `human_id_mint` - Human ID SBT minted (Optimism only)
- `passport_mint` - Passport minted on any chain
- `identity_staking_bronze/silver/gold` - Identity staking levels
- `community_staking_beginner/experienced/trusted` - Community staking levels

## Notes
- Points are calculated dynamically by joining with config table
- Multipliers are applied at query time for flexibility
- Binary actions (stamps) use unique constraints for deduplication
- Mint actions use tx_hash for deduplication
- All timestamps should be in UTC
- UI should re-query after on-chain mints with a 3-5 second delay

## Performance Considerations
- The three-way join (actions + config + multiplier) is efficient with proper indexes
- Config table is small and will be cached in memory
- Multiplier table uses primary key lookup (O(1))
- Consider materialized views for analytics/reporting use cases
- For high-traffic endpoints, implement caching at the API level

## Temporary Nature
This implementation is temporary for the points program duration. Consider:
- Feature flag to enable/disable points tracking
- Easy way to stop tracking without breaking existing functionality
- Clean separation from core logic
- Config table allows changing point values without code changes

## ✅ All Implementation Tasks Completed

### 1. Feature Flag Implementation (High Priority) ✅ COMPLETED
Add a feature flag to control Human Points functionality:

**Settings Configuration:**
```python
# In settings.py or environment-specific settings
HUMAN_POINTS_ENABLED = env.bool("HUMAN_POINTS_ENABLED", default=True)
```

**Scoring Integration Update:**
```python
# In registry/atasks.py, wrap the Human Points logic:
if settings.HUMAN_POINTS_ENABLED and community.human_points_program and score.score and score.score >= Decimal("20"):
    # Record passing score for this community
    await arecord_passing_score(address, community.pk)
    
    # Award human points for valid stamps
    await arecord_stamp_actions(address, deduped_passport_data.get("stamps", []))
    
    # Check and award scoring bonus if qualified
    await acheck_and_award_scoring_bonus(address, community.pk)
```

**API Response Update:**
```python
# In v2/api/api_stamps.py, conditionally include points_data:
points_data = None
if settings.HUMAN_POINTS_ENABLED and community.human_points_program:
    points_data = await aget_user_points_data(address_lower)

# Also update ceramic_cache/api/v1.py similarly
```

### 2. Multiplier Backfill Management Command (Medium Priority) ✅ COMPLETED
Create a management command to identify and reward returning users:

**File:** `api/registry/management/commands/backfill_human_points_multipliers.py`
```python
from django.core.management.base import BaseCommand
from django.db import transaction
from account.models import Community
from registry.models import Score, HumanPointsMultiplier, HumanPointsCommunityQualifiedUsers

class Command(BaseCommand):
    help = 'Backfill multipliers for returning users based on passing scores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        # Find all addresses with passing scores in human_points_program communities
        qualified_addresses = (
            HumanPointsCommunityQualifiedUsers.objects
            .values_list('address', flat=True)
            .distinct()
        )
        
        # Filter for addresses that don't already have multipliers
        existing_multipliers = HumanPointsMultiplier.objects.values_list('address', flat=True)
        addresses_to_create = set(qualified_addresses) - set(existing_multipliers)
        
        self.stdout.write(f"Found {len(addresses_to_create)} addresses needing multipliers")
        
        if not options['dry_run']:
            # Bulk create multipliers
            multipliers = [
                HumanPointsMultiplier(address=addr, multiplier=2)
                for addr in addresses_to_create
            ]
            HumanPointsMultiplier.objects.bulk_create(
                multipliers,
                ignore_conflicts=True
            )
            self.stdout.write(self.style.SUCCESS(f"Created {len(multipliers)} multipliers"))
        else:
            self.stdout.write("Dry run - no changes made")
```

### 3. Human Keys Nullifier Investigation (Low Priority) ✅ COMPLETED
Verify the structure of Human Keys credentials and update extraction if needed:

1. **Research:** Check the actual credential structure for humanKeysProvider stamps
2. **Update:** Modify the nullifier extraction logic in `human_points_utils.py` if needed

**Investigation Results:**
After examining the deduplication code in `account/deduplication/lifo.py`, the nullifier extraction has been updated to follow the same pattern:
- Primary case: `credential.credentialSubject.hash` 
- Multi-nullifier case: `credential.credentialSubject.nullifiers[0]`

The implementation in `human_points_utils.py` has been updated to correctly extract nullifiers from the `credentialSubject` field.

### 4. Initial Data Population ✅ COMPLETED
Create fixtures or data migration for HumanPointsConfig:

**File:** `api/registry/fixtures/human_points_config.json`
```json
[
  {"model": "registry.humanpointsconfig", "fields": {"action": "SCB", "points": 500, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "HKY", "points": 100, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "ISB", "points": 100, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "ISS", "points": 200, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "ISG", "points": 500, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "CSB", "points": 100, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "CSE", "points": 200, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "CST", "points": 500, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "PMT", "points": 300, "active": true}},
  {"model": "registry.humanpointsconfig", "fields": {"action": "HIM", "points": 1000, "active": true}}
]
```

Load with: `python manage.py loaddata human_points_config`

**Alternative: Data Migration**
A data migration (0050_populate_human_points_config.py) has also been created that will automatically populate the HumanPointsConfig table when migrations are run. This is the preferred method for production deployments.

### Testing Checklist
- [ ] Test feature flag enables/disables Human Points in scoring
- [ ] Test feature flag controls API response points_data field
- [ ] Test multiplier backfill command with --dry-run
- [ ] Test multiplier backfill command creates correct records
- [ ] Verify Human Keys nullifier extraction with real credentials
