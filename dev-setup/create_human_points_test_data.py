#!/usr/bin/env python
"""
Create Human Points test data for comparison tests.

This script creates:
- HumanPointsConfig entries for all action types
- Test data for verifying human points are recorded correctly
"""
import os
import sys
import django

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
api_path = os.path.join(project_root, 'api')
sys.path.insert(0, api_path)

env_file = os.path.join(project_root, '.env.development')
if os.path.exists(env_file):
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scorer.settings')
django.setup()

from registry.models import HumanPointsConfig, HumanPoints, HumanPointsCommunityQualifiedUsers
from account.models import Community

TEST_ADDRESS = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

print("Creating Human Points test data...\n")

# ============================================================================
# 1. HUMAN POINTS CONFIG
# ============================================================================
print("=== Human Points Config ===")

# Point values for each action type
POINT_VALUES = {
    HumanPoints.Action.SCORING_BONUS: 100,
    HumanPoints.Action.HUMAN_KEYS: 10,
    HumanPoints.Action.IDENTITY_STAKING_BRONZE: 50,
    HumanPoints.Action.IDENTITY_STAKING_SILVER: 100,
    HumanPoints.Action.IDENTITY_STAKING_GOLD: 200,
    HumanPoints.Action.COMMUNITY_STAKING_BEGINNER: 25,
    HumanPoints.Action.COMMUNITY_STAKING_EXPERIENCED: 50,
    HumanPoints.Action.COMMUNITY_STAKING_TRUSTED: 100,
    HumanPoints.Action.PASSPORT_MINT: 50,
    HumanPoints.Action.HUMAN_ID_MINT: 0,  # Excluded from point calculations
    HumanPoints.Action.HUMAN_TECH_GOV_ID: 150,
    HumanPoints.Action.HUMAN_TECH_PHONE: 75,
    HumanPoints.Action.HUMAN_TECH_PROOF_OF_CLEAN_HANDS: 100,
    HumanPoints.Action.HUMAN_TECH_BIOMETRIC: 200,
    HumanPoints.Action.METAMASK_OG: 500,
    HumanPoints.Action.METAMASK_OG_2: 500,
    HumanPoints.Action.SEASONED_PASSPORT_OG: 250,
    HumanPoints.Action.THE_CHOSEN_ONE: 1000,
}

for action, points in POINT_VALUES.items():
    config, created = HumanPointsConfig.objects.update_or_create(
        action=action,
        defaults={'points': points, 'active': True}
    )
    status = "created" if created else "updated"
    print(f"✓ {action}: {points} points ({status})")

# ============================================================================
# 2. ENABLE HUMAN POINTS ON COMMUNITY
# ============================================================================
print("\n=== Community Configuration ===")

# Enable human points program on community ID 1
community = Community.objects.get(id=1)
if not community.human_points_program:
    community.human_points_program = True
    community.save()
    print(f"✓ Enabled human_points_program on community {community.id}")
else:
    print(f"✓ Community {community.id} already has human_points_program enabled")

print("\n" + "="*60)
print("Human Points test data created successfully!")
print("="*60)
print("\nNext steps:")
print("1. Ensure HUMAN_POINTS_ENABLED=true in .env.development")
print("2. Set HUMAN_POINTS_START_TIMESTAMP=0 (or past timestamp)")
print("3. Run comparison tests to verify human points are recorded")
print("\nNote: Human points are recorded during scoring, not in responses")
print("      Check registry_humanpoints table to verify data")
