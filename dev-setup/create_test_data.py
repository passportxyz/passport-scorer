#!/usr/bin/env python
import os
import sys
import django
from decimal import Decimal
import json

# Setup Django - work from either location
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
api_path = os.path.join(project_root, 'api')
sys.path.insert(0, api_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scorer.settings')
# Use environment variable if set, otherwise use default
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev'
django.setup()

from account.models import Community, Account, AccountAPIKey
from scorer_weighted.models import BinaryWeightedScorer, Scorer
from ceramic_cache.models import CeramicCache
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

print("Creating test data using Django ORM...")

# Create a test user
test_user, created = User.objects.get_or_create(
    username='testuser',
    defaults={
        'email': 'test@example.com',
        'last_login': timezone.now()
    }
)
if created:
    print(f"Created test user: {test_user.username}")
else:
    print(f"Test user already exists: {test_user.username}")

# Create a test account
account, created = Account.objects.get_or_create(
    user=test_user,
    defaults={'address': '0x' + '1' * 40}
)
if created:
    print(f"Created test account: {account.address}")
else:
    print(f"Test account already exists: {account.address}")

# Create test scorers and communities
for i in range(1, 4):
    # First create the base Scorer
    scorer, scorer_created = Scorer.objects.get_or_create(
        id=i,
        defaults={'type': 'BinaryWeightedScorer'}
    )
    if scorer_created:
        print(f"Created base scorer {i}")

    # Then create the BinaryWeightedScorer
    weights = {
        "Google": "1.0",
        "Twitter": "1.0",
        "Github": "2.0",
        "Linkedin": "1.5",
        "Discord": "0.5",
        "Ens": "2.0"
    }

    binary_scorer, bs_created = BinaryWeightedScorer.objects.get_or_create(
        scorer_ptr_id=i,
        defaults={
            'weights': weights,
            'threshold': Decimal('2.5')
        }
    )
    if bs_created:
        print(f"Created binary weighted scorer for scorer {i}")
    else:
        print(f"Binary weighted scorer {i} already exists")

    # Now create the community
    # First check if a community already exists for this scorer
    try:
        community = Community.objects.get(scorer_id=i)
        print(f"Community already exists: {community.name}")
        comm_created = False
    except Community.DoesNotExist:
        # Create new community
        community = Community.objects.create(
            scorer_id=i,
            account=account,
            name=f'Test Community {i}',
            description=f'Test community {i} for development',
            use_case='sybil_protection',
            rule='LIFO'
        )
        print(f"Created community: {community.name}")
        comm_created = True

# Create test API keys
api_keys_created = []
for i in range(1, 3):
    key_name = f"Test API Key {i}"

    # Check if key with this name already exists
    existing = AccountAPIKey.objects.filter(account=account, name=key_name).first()
    if not existing:
        api_key_obj, api_key_string = AccountAPIKey.objects.create_key(
            account=account,
            name=key_name
        )
        api_keys_created.append(api_key_string)
        print(f"Created API key {i}: {api_key_string}")
    else:
        print(f"API key '{key_name}' already exists")

# Add some test ceramic cache entries (skip if table doesn't exist)
try:
    test_addresses = [
        '0x' + '2' * 40,
        '0x' + '3' * 40,
        '0x' + '4' * 40,
    ]

    for addr in test_addresses:
        stamps_created = 0
        for provider in ['Google', 'Twitter', 'Github']:
            stamp = {
                "provider": provider,
                "credential": {
                    "type": ["VerifiableCredential"],
                    "proof": {
                        "type": "Ed25519Signature2018",
                        "proofPurpose": "assertionMethod",
                        "verificationMethod": "did:key:test#test",
                        "signature": "test_signature"
                    },
                    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
                    "issuanceDate": "2023-01-01T00:00:00Z",
                    "expirationDate": "2024-01-01T00:00:00Z",
                    "credentialSubject": {
                        "id": f"did:ethr:{addr}",
                        "provider": provider,
                        "nullifiers": [f"v0-nullifier-{provider}-{addr}"],
                        "@context": {}
                    }
                }
            }

            cache_entry, created = CeramicCache.objects.get_or_create(
                address=addr.lower(),
                provider=provider,
                defaults={
                    'stamp': stamp,
                    'type': CeramicCache.StampType.V1
                }
            )
            if created:
                stamps_created += 1

        if stamps_created > 0:
            print(f"Created {stamps_created} stamps for address: {addr}")
        else:
            print(f"Stamps already exist for address: {addr}")
except Exception as e:
    print(f"Warning: Could not create ceramic cache entries: {e}")
    test_addresses = []

print("\n=== Test Data Summary ===")
print(f"Test user: testuser")
print(f"Test account: {account.address}")
print(f"Communities created: 1, 2, 3")
print(f"Test addresses with stamps: {', '.join(test_addresses)}")

if api_keys_created:
    print(f"\n=== New API Keys Created (save these!) ===")
    for i, key in enumerate(api_keys_created, 1):
        print(f"API Key {i}: {key}")

print("\nTest data creation complete!")