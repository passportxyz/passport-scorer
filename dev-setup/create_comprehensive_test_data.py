#!/usr/bin/env python
"""
Create comprehensive test data for comparison tests.

This script creates realistic test data for all endpoints to ensure
the comparison tests actually exercise the code paths and SQL queries.
"""
import os
import sys
import django
from decimal import Decimal
from datetime import datetime, timedelta

# Setup Django
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
api_path = os.path.join(project_root, 'api')
sys.path.insert(0, api_path)

# Load .env.development file
env_file = os.path.join(project_root, '.env.development')
if os.path.exists(env_file):
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scorer.settings')
django.setup()

from account.models import AddressList, AddressListMember
from ceramic_cache.models import Ban, Revocation
from stake.models import Stake
from cgrants.models import (
    GrantContributionIndex,
    ProtocolContributions,
    SquelchedAccounts,
    RoundMapping
)
from django.utils import timezone

print("Creating comprehensive test data for comparison tests...")

# Test address from test_config.json
TEST_ADDRESS = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Additional test addresses for various scenarios
BANNED_ADDRESS = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
REVOKED_ADDRESS = "0xcccccccccccccccccccccccccccccccccccccccc"
CONTRIBUTOR_ADDRESS = "0xdddddddddddddddddddddddddddddddddddddddd"

print("\n=== 1. Creating Allow List Data ===")
# Create a test allow list with memberships
test_list, created = AddressList.objects.get_or_create(name='testlist')  # No spaces, alphanumeric only
if created:
    print(f"Created allow list: {test_list.name}")
else:
    print(f"Allow list already exists: {test_list.name}")

# Add test address to the allow list
member, created = AddressListMember.objects.get_or_create(
    list=test_list,
    address=TEST_ADDRESS.lower()
)
if created:
    print(f"  Added {TEST_ADDRESS} to allow list")
else:
    print(f"  {TEST_ADDRESS} already in allow list")

print("\n=== 2. Creating Ban Data ===")
# Create an active ban for a test address (account-level ban)
ban, created = Ban.objects.get_or_create(
    address=BANNED_ADDRESS.lower(),
    type='account',
    defaults={
        'end_time': timezone.now() + timedelta(days=30)  # Active for 30 days
    }
)
if created:
    print(f"Created active account ban for {BANNED_ADDRESS}")
else:
    print(f"Account ban already exists for {BANNED_ADDRESS}")

# Create an expired ban (for testing that expired bans are ignored)
expired_ban, created = Ban.objects.get_or_create(
    address=TEST_ADDRESS.lower(),
    type='account',
    defaults={
        'end_time': timezone.now() - timedelta(days=1)  # Expired yesterday
    }
)
if created:
    print(f"Created expired ban for {TEST_ADDRESS}")
else:
    print(f"Expired ban already exists for {TEST_ADDRESS}")

# Create a single stamp ban (address + provider)
single_stamp_ban, created = Ban.objects.get_or_create(
    address=TEST_ADDRESS.lower(),
    provider='Google',
    type='single_stamp',
    defaults={
        'end_time': timezone.now() + timedelta(days=30)
    }
)
if created:
    print(f"Created single stamp ban for {TEST_ADDRESS} + Google")
else:
    print(f"Single stamp ban already exists")

print("\n=== 3. Creating Revocation Data ===")
# Note: Revocations require ceramic_cache_id, so we skip creating them here
# The check-revocations endpoint will return empty results for test proof values
print("Skipping revocations (require ceramic cache entries)")

print("\n=== 4. Creating GTC Stake Data ===")
# Create GTC stakes for test address (chain=1 for Ethereum mainnet)
stake1, created = Stake.objects.get_or_create(
    chain=1,  # Ethereum mainnet
    staker=TEST_ADDRESS.lower(),
    stakee=TEST_ADDRESS.lower(),
    defaults={
        'lock_time': timezone.now() - timedelta(days=30),
        'unlock_time': timezone.now() + timedelta(days=60),
        'last_updated_in_block': 12345678,
        'current_amount': Decimal('1000.50')
    }
)
if created:
    print(f"Created self-stake for {TEST_ADDRESS}: 1000.50 GTC")
else:
    print(f"Self-stake already exists for {TEST_ADDRESS}")

# Create community stake (someone else staking for test address)
stake2, created = Stake.objects.get_or_create(
    chain=1,  # Ethereum mainnet
    staker='0x1111111111111111111111111111111111111111',
    stakee=TEST_ADDRESS.lower(),
    defaults={
        'lock_time': timezone.now() - timedelta(days=15),
        'unlock_time': timezone.now() + timedelta(days=45),
        'last_updated_in_block': 12345680,
        'current_amount': Decimal('500.25')
    }
)
if created:
    print(f"Created community stake for {TEST_ADDRESS}: 500.25 GTC")
else:
    print(f"Community stake already exists for {TEST_ADDRESS}")

print("\n=== 5. Creating CGrants Contribution Data ===")

# First, create round mappings
round1, created = RoundMapping.objects.get_or_create(
    round_number='GG18',
    round_eth_address='0x5555555555555555555555555555555555555555'
)
if created:
    print(f"Created round mapping: GG18")

round2, created = RoundMapping.objects.get_or_create(
    round_number='GG19',
    round_eth_address='0x6666666666666666666666666666666666666666'
)
if created:
    print(f"Created round mapping: GG19")

# Create grant contribution data for CONTRIBUTOR_ADDRESS
# (Using realistic amounts and grant IDs)
contrib1, created = GrantContributionIndex.objects.get_or_create(
    contributor_address=CONTRIBUTOR_ADDRESS.lower(),
    grant_id=101,
    defaults={
        'round_num': 18,
        'amount': Decimal('25.50'),
        'profile_id': None,
        'contribution_id': None
    }
)
if created:
    print(f"Created grant contribution: Grant 101, $25.50")

contrib2, created = GrantContributionIndex.objects.get_or_create(
    contributor_address=CONTRIBUTOR_ADDRESS.lower(),
    grant_id=102,
    defaults={
        'round_num': 18,
        'amount': Decimal('50.00'),
        'profile_id': None,
        'contribution_id': None
    }
)
if created:
    print(f"Created grant contribution: Grant 102, $50.00")

contrib3, created = GrantContributionIndex.objects.get_or_create(
    contributor_address=CONTRIBUTOR_ADDRESS.lower(),
    grant_id=103,
    defaults={
        'round_num': 19,
        'amount': Decimal('100.75'),
        'profile_id': None,
        'contribution_id': None
    }
)
if created:
    print(f"Created grant contribution: Grant 103, $100.75")

# Create protocol contributions (Allo v2 contributions)
protocol1, created = ProtocolContributions.objects.get_or_create(
    ext_id=f'protocol_contrib_1_{CONTRIBUTOR_ADDRESS[:10]}',
    defaults={
        'contributor': CONTRIBUTOR_ADDRESS.lower(),
        'round': round1.round_eth_address,
        'project': '0x7777777777777777777777777777777777777777',
        'amount': Decimal('15.50'),
        'data': {}
    }
)
if created:
    print(f"Created protocol contribution: Round GG18, $15.50")

protocol2, created = ProtocolContributions.objects.get_or_create(
    ext_id=f'protocol_contrib_2_{CONTRIBUTOR_ADDRESS[:10]}',
    defaults={
        'contributor': CONTRIBUTOR_ADDRESS.lower(),
        'round': round2.round_eth_address,
        'project': '0x8888888888888888888888888888888888888888',
        'amount': Decimal('30.00'),
        'data': {}
    }
)
if created:
    print(f"Created protocol contribution: Round GG19, $30.00")

# Create a low-value contribution (< 0.95) that should be filtered out
protocol3, created = ProtocolContributions.objects.get_or_create(
    ext_id=f'protocol_contrib_3_{CONTRIBUTOR_ADDRESS[:10]}',
    defaults={
        'contributor': CONTRIBUTOR_ADDRESS.lower(),
        'round': round1.round_eth_address,
        'project': '0x9999999999999999999999999999999999999999',
        'amount': Decimal('0.50'),  # Below threshold
        'data': {}
    }
)
if created:
    print(f"Created low-value protocol contribution: $0.50 (should be filtered)")

# Create squelched account (sybil detection)
squelched, created = SquelchedAccounts.objects.get_or_create(
    address='0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
    round_number='GG18',
    defaults={
        'score_when_squelched': Decimal('5.0'),
        'sybil_signal': True
    }
)
if created:
    print(f"Created squelched account for GG18")

print("\n" + "="*60)
print("✅ Comprehensive test data creation complete!")
print("="*60)
print(f"""
Summary of test data created:
- Allow list: {TEST_ADDRESS} is in 'testlist'
- Bans: {BANNED_ADDRESS} has active ban, {TEST_ADDRESS} has expired ban + single stamp ban
- Revocations: Skipped (require ceramic cache entries)
- GTC Stakes: {TEST_ADDRESS} has 2 stake records (1500.75 GTC total)
- CGrants: {CONTRIBUTOR_ADDRESS} has:
  - 3 grant contributions ($176.25 total across 3 grants)
  - 2 valid protocol contributions ($45.50 total across 2 projects)
  - 1 low-value contribution (filtered out)
- Squelched: 1 address squelched in GG18
""")

print("\nTest addresses:")
print(f"  Main test address:  {TEST_ADDRESS}")
print(f"  Banned address:     {BANNED_ADDRESS}")
print(f"  Revoked address:    {REVOKED_ADDRESS}")
print(f"  Contributor address: {CONTRIBUTOR_ADDRESS}")
