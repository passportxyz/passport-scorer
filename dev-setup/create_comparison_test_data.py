#!/usr/bin/env python
"""
Create all test data needed for comparison tests.

This script creates:
- Allow lists and memberships
- Bans (active, expired, single stamp)
- GTC stakes (self and community)
- CGrants contributions (grant + protocol)
- Revocations (ceramic cache + revocation records)
"""
import os
import sys
import django
from decimal import Decimal
from datetime import timedelta

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

from account.models import AddressList, AddressListMember
from ceramic_cache.models import Ban, Revocation, CeramicCache
from stake.models import Stake
from cgrants.models import GrantContributionIndex, ProtocolContributions, SquelchedAccounts, RoundMapping
from django.utils import timezone
from django.db import connection

TEST_ADDRESS = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
BANNED_ADDRESS = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
SQUELCHED_ADDRESS = "0xdddddddddddddddddddddddddddddddddddddddd"

print("Creating comparison test data...\n")

# ============================================================================
# 1. ALLOW LISTS
# ============================================================================
print("=== Allow Lists ===")
test_list, _ = AddressList.objects.get_or_create(name='testlist')
AddressListMember.objects.get_or_create(list=test_list, address=TEST_ADDRESS.lower())
print(f"✓ {TEST_ADDRESS} added to 'testlist'")

# ============================================================================
# 2. BANS
# ============================================================================
print("\n=== Bans ===")
# Active account-level ban
Ban.objects.get_or_create(
    address=BANNED_ADDRESS.lower(),
    type='account',
    defaults={'end_time': timezone.now() + timedelta(days=30)}
)
print(f"✓ Active ban for {BANNED_ADDRESS}")

# Expired ban (should be ignored by endpoint)
Ban.objects.get_or_create(
    address=TEST_ADDRESS.lower(),
    type='account',
    defaults={'end_time': timezone.now() - timedelta(days=1)}
)
print(f"✓ Expired ban for {TEST_ADDRESS}")

# Single stamp ban (provider-specific)
Ban.objects.get_or_create(
    address=TEST_ADDRESS.lower(),
    provider='Google',
    type='single_stamp',
    defaults={'end_time': timezone.now() + timedelta(days=30)}
)
print(f"✓ Single stamp ban for {TEST_ADDRESS} + Google")

# ============================================================================
# 3. GTC STAKES
# ============================================================================
print("\n=== GTC Stakes ===")
# Self-stake
Stake.objects.get_or_create(
    chain=1,
    staker=TEST_ADDRESS.lower(),
    stakee=TEST_ADDRESS.lower(),
    defaults={
        'lock_time': timezone.now() - timedelta(days=30),
        'unlock_time': timezone.now() + timedelta(days=60),
        'last_updated_in_block': 12345678,
        'current_amount': Decimal('1000.50')
    }
)
print(f"✓ Self-stake: {TEST_ADDRESS} → {TEST_ADDRESS}: 1000.50 GTC")

# Community stake (someone else staking for test address)
Stake.objects.get_or_create(
    chain=1,
    staker='0x1111111111111111111111111111111111111111',
    stakee=TEST_ADDRESS.lower(),
    defaults={
        'lock_time': timezone.now() - timedelta(days=15),
        'unlock_time': timezone.now() + timedelta(days=45),
        'last_updated_in_block': 12345680,
        'current_amount': Decimal('500.25')
    }
)
print(f"✓ Community stake: 0x1111... → {TEST_ADDRESS}: 500.25 GTC")
print(f"  Total GTC for {TEST_ADDRESS}: 1500.75")

# ============================================================================
# 4. CGRANTS DATA
# ============================================================================
print("\n=== CGrants Data ===")
with connection.cursor() as cursor:
    # Create minimal profile for FK constraint
    cursor.execute("""
        INSERT INTO cgrants_profile (handle, github_id, notes, data)
        VALUES ('test_user', 12345, 'Test profile', '{}')
        ON CONFLICT (handle) DO NOTHING
        RETURNING id
    """)
    result = cursor.fetchone()
    if result:
        profile_id = result[0]
        print(f"✓ Created test profile (id={profile_id})")
    else:
        cursor.execute("SELECT id FROM cgrants_profile WHERE handle = 'test_user'")
        profile_id = cursor.fetchone()[0]
        print(f"✓ Using existing test profile (id={profile_id})")

    # Create grants for FK constraint
    for grant_id in [101, 102, 103]:
        cursor.execute("""
            INSERT INTO cgrants_grant (id, admin_profile_id, hidden, active, is_clr_eligible, data)
            VALUES (%s, %s, false, true, true, '{}')
            ON CONFLICT (id) DO NOTHING
        """, [grant_id, profile_id])
    print("✓ Created test grants (101, 102, 103)")

    # Create round mappings
    cursor.execute("""
        INSERT INTO cgrants_roundmapping (round_number, round_eth_address)
        VALUES ('GG18', '0x5555555555555555555555555555555555555555')
        ON CONFLICT (round_number, round_eth_address) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO cgrants_roundmapping (round_number, round_eth_address)
        VALUES ('GG19', '0x6666666666666666666666666666666666666666')
        ON CONFLICT (round_number, round_eth_address) DO NOTHING
    """)
    print("✓ Created round mappings: GG18, GG19")

    # Create grant contribution index entries
    cursor.execute("""
        INSERT INTO cgrants_grantcontributionindex
        (contributor_address, grant_id, round_num, amount, profile_id, contribution_id)
        VALUES (%s, 101, 18, %s, %s, NULL)
        ON CONFLICT DO NOTHING
    """, [TEST_ADDRESS.lower(), Decimal('25.50'), profile_id])

    cursor.execute("""
        INSERT INTO cgrants_grantcontributionindex
        (contributor_address, grant_id, round_num, amount, profile_id, contribution_id)
        VALUES (%s, 102, 18, %s, %s, NULL)
        ON CONFLICT DO NOTHING
    """, [TEST_ADDRESS.lower(), Decimal('50.00'), profile_id])

    cursor.execute("""
        INSERT INTO cgrants_grantcontributionindex
        (contributor_address, grant_id, round_num, amount, profile_id, contribution_id)
        VALUES (%s, 103, 19, %s, %s, NULL)
        ON CONFLICT DO NOTHING
    """, [TEST_ADDRESS.lower(), Decimal('100.75'), profile_id])

    print(f"✓ Created 3 grant contributions for {TEST_ADDRESS}: $176.25 total")

    # Create protocol contributions
    cursor.execute("""
        INSERT INTO cgrants_protocolcontributions
        (ext_id, contributor, round, project, amount, data)
        VALUES ('tx_test_1', %s, '0x5555555555555555555555555555555555555555',
                '0xaaaa111111111111111111111111111111111111', %s, '{}')
        ON CONFLICT (ext_id) DO NOTHING
    """, [TEST_ADDRESS.lower(), Decimal('15.00')])

    cursor.execute("""
        INSERT INTO cgrants_protocolcontributions
        (ext_id, contributor, round, project, amount, data)
        VALUES ('tx_test_2', %s, '0x6666666666666666666666666666666666666666',
                '0xaaaa222222222222222222222222222222222222', %s, '{}')
        ON CONFLICT (ext_id) DO NOTHING
    """, [TEST_ADDRESS.lower(), Decimal('30.50')])

    print(f"✓ Created 2 protocol contributions for {TEST_ADDRESS}: $45.50 total")

    # Create a squelched account for testing exclusion
    cursor.execute("""
        INSERT INTO cgrants_squelchedaccounts
        (address, score_when_squelched, sybil_signal, round_number)
        VALUES (%s, 0, true, 'GG18')
        ON CONFLICT DO NOTHING
    """, [SQUELCHED_ADDRESS.lower()])

    print(f"✓ Created squelched account for {SQUELCHED_ADDRESS} in GG18")

    # Create contributions for squelched account (should be excluded)
    cursor.execute("""
        INSERT INTO cgrants_protocolcontributions
        (ext_id, contributor, round, project, amount, data)
        VALUES ('tx_squelched', %s, '0x5555555555555555555555555555555555555555',
                '0xaaaa333333333333333333333333333333333333', %s, '{}')
        ON CONFLICT (ext_id) DO NOTHING
    """, [SQUELCHED_ADDRESS.lower(), Decimal('1000.00')])

    print(f"✓ Created squelched contribution (will be excluded from stats)")

print(f"  Expected for {TEST_ADDRESS}: 5 grants/projects, $221.75 total")

# ============================================================================
# 5. REVOCATIONS
# ============================================================================
print("\n=== Revocations ===")
# Create ceramic cache entries to reference
cc1, created = CeramicCache.objects.get_or_create(
    address=TEST_ADDRESS.lower(),
    provider='RevokedProvider1',
    defaults={
        'type': CeramicCache.StampType.V1,
        'proof_value': 'revoked_proof_1',
        'stamp': {
            'proof': {
                'proofValue': 'revoked_proof_1'
            },
            'credentialSubject': {
                'provider': 'RevokedProvider1',
                'hash': 'revoked_hash_1'
            }
        }
    }
)
if created:
    print(f"✓ Created ceramic cache entry for RevokedProvider1")

cc2, created = CeramicCache.objects.get_or_create(
    address=TEST_ADDRESS.lower(),
    provider='RevokedProvider2',
    defaults={
        'type': CeramicCache.StampType.V1,
        'proof_value': 'revoked_proof_2',
        'stamp': {
            'proof': {
                'proofValue': 'revoked_proof_2'
            },
            'credentialSubject': {
                'provider': 'RevokedProvider2',
                'hash': 'revoked_hash_2'
            }
        }
    }
)
if created:
    print(f"✓ Created ceramic cache entry for RevokedProvider2")

# Create revocations for these proof values
rev1, created = Revocation.objects.get_or_create(
    proof_value='revoked_proof_1',
    defaults={'ceramic_cache': cc1}
)
if created:
    print(f"✓ Created revocation for proof value: revoked_proof_1")

rev2, created = Revocation.objects.get_or_create(
    proof_value='revoked_proof_2',
    defaults={'ceramic_cache': cc2}
)
if created:
    print(f"✓ Created revocation for proof value: revoked_proof_2")

print("\n" + "="*60)
print("✅ All comparison test data created successfully!")
print("="*60)
print("\nYou can now run comparison tests:")
print("  cd rust-scorer/comparison-tests && cargo run --release")
