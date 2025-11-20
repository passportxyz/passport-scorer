#!/usr/bin/env python
"""
Generate properly signed test credentials for comparison testing.
Uses DIDKit to sign credentials with a test issuer key.
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta, timezone

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

import django
django.setup()

import didkit
from asgiref.sync import sync_to_async
from account.models import Community, Account, AccountAPIKey
from scorer_weighted.models import BinaryWeightedScorer, Scorer
from ceramic_cache.models import CeramicCache
from django.contrib.auth import get_user_model

User = get_user_model()

# Wrap Django ORM operations for async
@sync_to_async
def get_or_create_user(username, defaults):
    return User.objects.get_or_create(username=username, defaults=defaults)

@sync_to_async
def get_or_create_account(user, defaults):
    return Account.objects.get_or_create(user=user, defaults=defaults)

@sync_to_async
def get_or_create_scorer(id, defaults):
    return Scorer.objects.get_or_create(id=id, defaults=defaults)

@sync_to_async
def update_or_create_binary_scorer(scorer_ptr_id, defaults):
    return BinaryWeightedScorer.objects.update_or_create(scorer_ptr_id=scorer_ptr_id, defaults=defaults)

@sync_to_async
def get_community(scorer_id):
    return Community.objects.get(scorer_id=scorer_id)

@sync_to_async
def create_community(**kwargs):
    return Community.objects.create(**kwargs)

@sync_to_async
def delete_ceramic_cache(address):
    return CeramicCache.objects.filter(address=address.lower()).delete()

@sync_to_async
def create_ceramic_cache(**kwargs):
    return CeramicCache.objects.create(**kwargs)

@sync_to_async
def get_ceramic_cache_entries(address):
    return list(CeramicCache.objects.filter(address=address.lower()))

@sync_to_async
def get_api_key_by_name(account, name):
    return AccountAPIKey.objects.filter(account=account, name=name).first()

@sync_to_async
def delete_api_key(api_key):
    return api_key.delete()

@sync_to_async
def create_api_key(account, name):
    return AccountAPIKey.objects.create_key(account=account, name=name)

async def create_signed_credential(address: str, provider: str, issuer_key: str, verification_method: str):
    """Create a properly signed verifiable credential."""

    now = datetime.now(timezone.utc)
    expiration = now + timedelta(days=90)

    # Extract issuer DID from verification method (everything before #)
    issuer_did = verification_method.split("#")[0]

    # Create the credential with proper JSON-LD context
    credential = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            {
                "provider": "https://schema.org/Text",
                "nullifiers": {
                    "@id": "https://schema.org/Text",
                    "@container": "@list"
                }
            }
        ],
        "type": ["VerifiableCredential"],
        "issuer": issuer_did,
        "issuanceDate": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expirationDate": expiration.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "credentialSubject": {
            "id": f"did:pkh:eip155:1:{address.lower()}",
            "provider": provider,
            # Use nullifiers array (required for Rust scorer)
            "nullifiers": [f"v0:{provider}:{address.lower()}:test-nullifier"]
        }
    }

    # Sign the credential with DIDKit
    proof_options = json.dumps({
        "proofPurpose": "assertionMethod",
        "verificationMethod": verification_method
    })

    # didkit functions are async
    signed_credential = await didkit.issue_credential(
        json.dumps(credential),
        proof_options,
        issuer_key
    )

    return json.loads(signed_credential)


async def main():
    print("\n=== Creating Test Credentials ===\n")

    # Use a hardcoded test issuer key (Ed25519 in JWK format) so TRUSTED_IAM_ISSUERS doesn't change
    # This key was generated once with didkit.generate_ed25519_key() and saved here
    # Corresponding DID: did:key:z6MkjUhQJSaMUg8356Jk8dyCpCdEPq9VpUrAYrTrn5ZntgMM
    issuer_key = '{"kty":"OKP","crv":"Ed25519","x":"Sqiv0IDVlmmu99MtT9NMbncFEbajG41VyBgQHmcEbWA","d":"5hPR9layEeB5TAdFfna5yQPR4RMIigarCT73r9vcORc"}'
    issuer_did = didkit.key_to_did("key", issuer_key)
    # For did:key, the verification method is the DID with the key multibase as fragment
    verification_method = await didkit.key_to_verification_method("key", issuer_key)

    print(f"Test issuer DID: {issuer_did}")
    print(f"Test verification method: {verification_method}")

    # Ensure test user and account exist
    test_user, _ = await get_or_create_user(
        username='testuser',
        defaults={'email': 'test@example.com'}
    )

    account, _ = await get_or_create_account(
        user=test_user,
        defaults={'address': '0x' + '1' * 40}
    )

    # Create/verify scorer exists
    scorer, _ = await get_or_create_scorer(
        id=1,
        defaults={'type': 'WEIGHTED_BINARY'}
    )

    weights = {
        "Google": "1.0",
        "Twitter": "1.0",
        "Github": "2.0",
        "Linkedin": "1.5",
        "Discord": "0.5",
        "Ens": "2.0"
    }

    await update_or_create_binary_scorer(
        scorer_ptr_id=1,
        defaults={
            'weights': weights,
            'threshold': '2.5'
        }
    )

    # Ensure community exists
    try:
        community = await get_community(scorer_id=1)
    except Community.DoesNotExist:
        community = await create_community(
            scorer_id=1,
            account=account,
            name='Test Community 1',
            description='Test community for development',
            use_case='sybil_protection',
            rule='LIFO'
        )
        print(f"Created community: {community.name}")

    # Test address that will have stamps
    test_address = "0x" + "a" * 40  # 0xaaaa...

    # Providers with weights that will give score > 2.5 threshold
    # Google(1.0) + Twitter(1.0) + Github(2.0) = 4.0 > 2.5
    providers = ["Google", "Twitter", "Github"]

    # Clear existing stamps for this address
    await delete_ceramic_cache(test_address)
    print(f"Cleared existing stamps for {test_address}")

    # Create signed credentials
    credentials = []
    for provider in providers:
        credential = await create_signed_credential(
            test_address,
            provider,
            issuer_key,
            verification_method
        )
        credentials.append(credential)

        # Store in ceramic cache
        # Note: The CeramicCache.stamp field should contain just the credential,
        # not a wrapper with provider/credential keys. The aget_passport function
        # builds the stamp structure as {"provider": s.provider, "credential": s.stamp}
        await create_ceramic_cache(
            address=test_address.lower(),
            provider=provider,
            stamp=credential,  # Just the credential, not a wrapper
            type=CeramicCache.StampType.V1
        )
        print(f"Created signed credential for {provider}")

    # Verify the credentials are valid
    print("\nVerifying credentials...")
    entries = await get_ceramic_cache_entries(test_address)
    for entry in entries:
        # entry.stamp is now the credential directly
        cred = entry.stamp
        try:
            result = await didkit.verify_credential(
                json.dumps(cred),
                json.dumps({"proofPurpose": "assertionMethod"})
            )
            result_obj = json.loads(result)
            if result_obj.get("errors"):
                print(f"  {entry.provider}: INVALID - {result_obj['errors']}")
            else:
                print(f"  {entry.provider}: VALID")
        except Exception as e:
            print(f"  {entry.provider}: ERROR - {e}")

    # Create/get API key for tests
    key_name = "Comparison Test Key"
    existing = await get_api_key_by_name(account, key_name)

    if existing:
        # Can't retrieve the key, need to create a new one
        await delete_api_key(existing)

    api_key_obj, api_key_string = await create_api_key(account, key_name)

    # Save test configuration
    config = {
        "test_address": test_address.lower(),
        "scorer_id": 1,
        "api_key": api_key_string,
        "issuer_did": issuer_did,
        "providers": providers,
        "expected_score_above": 2.5,
        "credentials": credentials
    }

    config_path = os.path.join(project_root, "rust-scorer", "comparison-tests", "test_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n=== Test Configuration ===")
    print(f"Test address: {test_address}")
    print(f"Scorer ID: 1")
    print(f"API Key: {api_key_string}")
    print(f"Issuer DID: {issuer_did}")
    print(f"Config saved to: {config_path}")

    # Important: Add the test issuer to TRUSTED_IAM_ISSUERS
    print(f"\n=== IMPORTANT ===")
    print(f"Add this DID to TRUSTED_IAM_ISSUERS in .env.development:")
    print(f'TRUSTED_IAM_ISSUERS=\'["{issuer_did}"]\'')

    return config


if __name__ == "__main__":
    config = asyncio.run(main())
    print("\nTest credential creation complete!")
