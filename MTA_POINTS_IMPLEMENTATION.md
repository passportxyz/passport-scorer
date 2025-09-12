# MetaMask OG Points Implementation Plan

## Overview
Add support for awarding HUMN points to MetaMask OG users who are on a pre-defined address list and have achieved a passing Passport score (20+). This is a one-time campaign limited to the first 5,000 eligible addresses.

## Implementation Steps

### 1. Add New Action Type
**File:** `api/registry/models.py` (line ~376, in `HumanPoints.Action` class)

Add the new action type:
```python
MTA = "MTA"  # MetaMask OG users
```

### 2. Create Database Migration
Run Django migration to add the new action choice:
```bash
cd api/
python manage.py makemigrations registry
python manage.py migrate
```

### 3. Configure Points Value
Add a `HumanPointsConfig` entry for the MTA action with 1000 points:
- Via Django Admin: `/admin/registry/humanpointsconfig/`
- Or via Django shell:
```python
from registry.models import HumanPointsConfig, HumanPoints
HumanPointsConfig.objects.create(
    action=HumanPoints.Action.MTA,
    points=1000,
    active=True
)
```

### 4. Create Address List
1. Go to Django Admin: `/admin/account/addresslist/`
2. Create a new AddressList with name: **"MetaMask OG"** (exact name required)
3. Upload addresses via CSV import at `/admin/account/addresslist/import-csv/`
   - CSV should contain one address per line
   - First column should be the Ethereum address

### 5. Add Feature Flag
**File:** `api/scorer/settings/base.py` (or appropriate settings file)

Add:
```python
HUMAN_POINTS_MTA_ENABLED = env.bool("HUMAN_POINTS_MTA_ENABLED", default=False)
```

### 6. Implement Points Award Logic
**File:** `api/registry/atasks.py` (approximately line 269, after `await arecord_stamp_actions(...)`)

Add the following code inside the existing conditional block that checks for passing scores:
```python
# Award MTA points if on MetaMask OG list (limit 5000)
if settings.HUMAN_POINTS_MTA_ENABLED:
    try:
        mta_list = await AddressList.objects.aget(name="MetaMask OG")
        if await mta_list.addresses.filter(address=address).aexists():
            # Check if we've already awarded 5000 MTA points
            mta_count = await HumanPoints.objects.filter(
                action=HumanPoints.Action.MTA
            ).acount()
            
            if mta_count < 5000:
                await HumanPoints.objects.aget_or_create(
                    address=address,
                    action=HumanPoints.Action.MTA
                )
    except AddressList.DoesNotExist:
        pass
```

**Note:** Don't forget to import `AddressList` at the top of the file:
```python
from account.models import AccountAPIKeyAnalytics, Community, Rules, AddressList
```

### 7. Testing

#### Unit Test
Create a test in `api/registry/test/test_human_points_scoring_integration.py`:
```python
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
@patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", True)
async def test_mta_points_awarded_to_list_members():
    """Test that MTA points are awarded to addresses on the MetaMask OG list"""
    # Create address list
    mta_list = await AddressList.objects.acreate(name="MetaMask OG")
    await mta_list.addresses.acreate(address="0x123...")
    
    # Create HumanPointsConfig
    await HumanPointsConfig.objects.acreate(
        action=HumanPoints.Action.MTA,
        points=1000
    )
    
    # Score passport for address on list
    # ... scoring logic ...
    
    # Verify MTA points awarded
    mta_points = await HumanPoints.objects.filter(
        address="0x123...",
        action=HumanPoints.Action.MTA
    ).acount()
    assert mta_points == 1
```

#### Manual Testing
1. Set `HUMAN_POINTS_MTA_ENABLED=true` in environment
2. Create "MetaMask OG" AddressList with test addresses
3. Submit a passport for an address on the list with score >= 20
4. Verify MTA points are awarded in `HumanPoints` table
5. Verify only first 5000 addresses receive points (Maybe make this configurable with default 5000 to make testing easier?)
6. Make sure it is case-insensitive

## Deployment Steps

1. Deploy code with feature flag disabled
2. Run migrations
3. Add HumanPointsConfig entry for MTA (1000 points)
4. Upload MetaMask OG address list via admin
5. Enable feature flag: `HUMAN_POINTS_MTA_ENABLED=true`
6. Monitor HumanPoints table for MTA entries

## Rollback Plan

If issues arise:
1. Disable feature flag: `HUMAN_POINTS_MTA_ENABLED=false`
2. Optionally remove MTA points: 
   ```sql
   DELETE FROM registry_humanpoints WHERE action = 'MTA';
   ```

## Important Notes

- **Uniqueness:** The existing database constraint ensures each address can only receive MTA points once
- **5000 Limit:** First-come, first-served based on when users submit their passports for scoring
- **Eligibility:** Users must have a passing score (20+) in a community with `human_points_program=True`
- **One-time Campaign:** Once 5000 points are distributed, the feature can be disabled

## Monitoring

Monitor progress with:
```sql
-- Count of MTA points awarded
SELECT COUNT(*) FROM registry_humanpoints WHERE action = 'MTA';

-- List of addresses with MTA points
SELECT address, timestamp FROM registry_humanpoints 
WHERE action = 'MTA' 
ORDER BY timestamp;
```
