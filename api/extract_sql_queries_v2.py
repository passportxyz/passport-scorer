#!/usr/bin/env python
"""
Extract SQL queries from Django ORM for internal API endpoints - simplified version
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
sys.path.insert(0, '/workspace/project/api')
django.setup()

from django.db import connection
from django.db.models import Q, Count, Sum

print("EXTRACTING SQL QUERIES FROM DJANGO ORM")
print("="*80)

# 1. BAN QUERIES
print("\n1. /internal/check-bans")
print("-"*40)
from ceramic_cache.models import Ban
address = "0x1234567890abcdef1234567890abcdef12345678"
hashes = ["hash1", "hash2", "hash3"]

# Note: Using NOW() for comparison as runtime would use current time
print("Query 1: Get active bans")
print("""
SELECT * FROM ceramic_cache_ban
WHERE (address = %(address)s OR hash = ANY(%(hashes)s))
AND (end_time IS NULL OR end_time > NOW())
""")

# 2. REVOCATION QUERIES
print("\n2. /internal/check-revocations")
print("-"*40)
from ceramic_cache.models import Revocation
print("Query: Check if proof values are revoked")
print("""
SELECT proof_value FROM ceramic_cache_revocation
WHERE proof_value = ANY(%(proof_values)s)
""")

# 3. STAKE QUERIES
print("\n3. /internal/stake/gtc/{address}")
print("-"*40)
from stake.models import Stake
print("Query: Get GTC stakes")
print("""
SELECT id, chain, lock_time, unlock_time, last_updated_in_block,
       staker, stakee, current_amount
FROM stake_stake
WHERE staker = %(address)s OR stakee = %(address)s
""")

# 4. LEGACY STAKE QUERIES
print("\n4. /internal/stake/legacy-gtc/{address}/{round_id}")
print("-"*40)
from registry.models import GTCStakeEvent
print("Query: Get legacy GTC stakes")
print("""
SELECT * FROM registry_gtcstakeevent
WHERE round_id = %(round_id)s
AND (staker = %(address)s OR address = %(address)s)
""")

# 5. CGRANTS QUERIES
print("\n5. /internal/cgrants/contributor_statistics")
print("-"*40)
from cgrants.models import GrantContributionIndex, ProtocolContributions, SquelchedAccounts

print("Query 1: Check if address is squelched")
print("""
SELECT * FROM cgrants_squelchedaccounts
WHERE address = %(address)s
""")

print("\nQuery 2a: Count unique grants (cgrants)")
print("""
SELECT COUNT(DISTINCT grant_id) FROM cgrants_grantcontributionindex
WHERE contributor_address = %(address)s
AND contribution_id IN (
    SELECT id FROM cgrants_contribution
    WHERE success = true
)
""")

print("\nQuery 2b: Sum contribution amounts (cgrants)")
print("""
SELECT SUM(amount) FROM cgrants_grantcontributionindex
WHERE contributor_address = %(address)s
AND contribution_id IN (
    SELECT id FROM cgrants_contribution
    WHERE success = true
)
""")

print("\nQuery 3a: Protocol contributions - count rounds")
print("""
SELECT COUNT(DISTINCT round) FROM cgrants_protocolcontributions
WHERE from_address = %(address)s OR to_address = %(address)s
""")

print("\nQuery 3b: Protocol contributions - sum amounts FROM")
print("""
SELECT SUM(amount) FROM cgrants_protocolcontributions
WHERE from_address = %(address)s
""")

print("\nQuery 3c: Protocol contributions - sum amounts TO")
print("""
SELECT SUM(amount) FROM cgrants_protocolcontributions
WHERE to_address = %(address)s
""")

# 6. ALLOW LIST QUERIES
print("\n6. /internal/allow-list/{list}/{address}")
print("-"*40)
from account.models import AddressListMember
print("Query: Check if address is in list")
print("""
SELECT EXISTS(
    SELECT 1 FROM account_addresslistmember alm
    JOIN account_addresslist al ON alm.list_id = al.id
    WHERE al.name = %(list_name)s
    AND alm.address = %(address)s
)
""")

# 7. CUSTOMIZATION/CREDENTIAL QUERIES
print("\n7. /internal/customization/credential/{provider_id}")
print("-"*40)
from account.models import CustomCredentialRuleset
print("Query: Get custom credential definition")
print("""
SELECT definition FROM account_customcredentialruleset
WHERE provider_id = %(provider_id)s
""")

# 8. CERAMIC CACHE QUERIES (for reference)
print("\n8. Ceramic Cache Operations (embed endpoints)")
print("-"*40)
print("Query 1: Soft delete stamps by provider")
print("""
UPDATE ceramic_cache_ceramiccache
SET deleted_at = NOW()
WHERE address = %(address)s
AND provider = ANY(%(providers)s)
AND type = 'V1'
AND deleted_at IS NULL
""")

print("\nQuery 2: Get stamps from cache")
print("""
SELECT id, address, provider, stamp, created_at
FROM ceramic_cache_ceramiccache
WHERE address = %(address)s
AND type = 'V1'
AND deleted_at IS NULL
ORDER BY created_at DESC
""")

print("\nQuery 3: Insert stamp into cache")
print("""
INSERT INTO ceramic_cache_ceramiccache
(type, address, provider, stamp, proof_value,
 updated_at, compose_db_save_status,
 issuance_date, expiration_date, source_app)
VALUES
('V1', %(address)s, %(provider)s, %(stamp)s, %(proof_value)s,
 NOW(), 'pending', %(issuance_date)s, %(expiration_date)s, 2)
""")

print("\n" + "="*80)
print("NOTE: Parameters are shown as %(name)s for clarity")
print("In production, these would be bound parameters to prevent SQL injection")