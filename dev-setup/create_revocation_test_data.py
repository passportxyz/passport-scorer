#!/usr/bin/env python
"""
Create revocation test data for comparison tests.

Revocations track proof values that have been revoked.
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

from ceramic_cache.models import Revocation, CeramicCache
from django.utils import timezone

TEST_ADDRESS = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

print("Creating revocation test data...")

# First, we need ceramic cache entries to reference
# Let's create a couple of test ceramic cache entries
cc1, created = CeramicCache.objects.get_or_create(
    address=TEST_ADDRESS.lower(),
    provider='RevokedProvider1',
    defaults={
        'type': CeramicCache.StampType.V1,  # Use IntEnum value
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
        'type': CeramicCache.StampType.V1,  # Use IntEnum value
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

# Now create revocations for these proof values
rev1, created = Revocation.objects.get_or_create(
    proof_value='revoked_proof_1',
    defaults={
        'ceramic_cache': cc1
    }
)
if created:
    print(f"✓ Created revocation for proof value: revoked_proof_1")
else:
    print(f"  Revocation already exists for: revoked_proof_1")

rev2, created = Revocation.objects.get_or_create(
    proof_value='revoked_proof_2',
    defaults={
        'ceramic_cache': cc2
    }
)
if created:
    print(f"✓ Created revocation for proof value: revoked_proof_2")
else:
    print(f"  Revocation already exists for: revoked_proof_2")

print("\n✓ Revocation test data created!")
print(f"\nTest with these proof values:")
print(f"  - revoked_proof_1 (should be found)")
print(f"  - revoked_proof_2 (should be found)")
print(f"  - non_revoked_proof (should not be found)")
