"""
djangorestframework-api-key >= 3.0 stores API keys as "sha512$$<128 hex>"
(rest_framework_api_key.crypto.Sha512ApiKeyHasher). That format reaches the
database two ways:

1. AccountAPIKey.objects.create_key() writes it for every new key.
2. The library's AbstractAPIKey.is_valid() rewrites an existing key's legacy
   hash to it on first successful use, e.g. via get_from_key() in
   embed/lambda_fn.py.

FastAPIKeyValidator must accept it, or those keys get a plain 401 on the main API.
"""

import hashlib

import pytest
from django.contrib.auth.models import User
from django.test import Client

from account.api_key_validator import FastAPIKeyValidator, averify_key
from account.models import Account, AccountAPIKey

KEY = "abcd1234.secretvalue"
SHA512 = "sha512$$" + hashlib.sha512(KEY.encode()).hexdigest()


def test_verify_key_accepts_sha512_and_requests_migration():
    assert FastAPIKeyValidator.verify_key(KEY, SHA512, None) == (True, True)


def test_verify_key_rejects_wrong_key_for_sha512_hash():
    assert FastAPIKeyValidator.verify_key("abcd1234.wrong", SHA512, None) == (
        False,
        False,
    )


@pytest.mark.asyncio
async def test_async_verify_key_accepts_sha512():
    assert await averify_key(KEY, SHA512, None) == (True, True)


@pytest.mark.django_db
def test_key_stored_as_sha512_authenticates_end_to_end_and_migrates():
    user = User.objects.create_user(username="sha512-user", password="12345")
    account = Account.objects.create(user=user, address="0x" + "5" * 40)
    api_key, secret = AccountAPIKey.objects.create_key(account=account, name="k")

    # Store it exactly as drf-api-key 3.x would, with no SHA-256 fast path yet.
    api_key.hashed_key = "sha512$$" + hashlib.sha512(secret.encode()).hexdigest()
    api_key.hashed_key_sha256 = None
    api_key.save()

    response = Client().get("/registry/signing-message", HTTP_X_API_KEY=secret)

    assert response.status_code == 200
    api_key.refresh_from_db()
    assert api_key.hashed_key_sha256 == FastAPIKeyValidator.hash_key(secret)
