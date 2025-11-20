#!/usr/bin/env python
"""
Create CGrants test data using direct SQL to bypass complex FK constraints.

This script creates minimal test data for the CGrants contributor statistics endpoint
without needing to create all the FK dependencies (Profile, Grant, Subscription, etc).
"""
import os
import sys
import django
from decimal import Decimal

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

from django.db import connection

TEST_ADDRESS = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CONTRIBUTOR_ADDRESS = "0xdddddddddddddddddddddddddddddddddddddddd"

print("Creating CGrants test data...")

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
        # Profile already exists, get its ID
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

    # Create grant contribution index entries (now with profile_id and grant_id)
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
    """, [CONTRIBUTOR_ADDRESS.lower()])

    print(f"✓ Created squelched account for {CONTRIBUTOR_ADDRESS} in GG18")

    # Create contributions for squelched account (should be excluded)
    cursor.execute("""
        INSERT INTO cgrants_protocolcontributions
        (ext_id, contributor, round, project, amount, data)
        VALUES ('tx_squelched', %s, '0x5555555555555555555555555555555555555555',
                '0xaaaa333333333333333333333333333333333333', %s, '{}')
        ON CONFLICT (ext_id) DO NOTHING
    """, [CONTRIBUTOR_ADDRESS.lower(), Decimal('1000.00')])

    print(f"✓ Created squelched contribution (will be excluded from stats)")

print("\n✓ CGrants test data created!")
print(f"\nExpected results for {TEST_ADDRESS}:")
print(f"  - Grant contributions: 3 grants, $176.25 total")
print(f"  - Protocol contributions: 2 projects, $45.50 total")
print(f"  - Combined: 5 grants/projects, $221.75 total")
