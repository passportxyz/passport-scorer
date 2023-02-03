"""Claim of Stamps in Scorer database via API call feature tests."""

import json

import pytest
from ceramic_cache.models import CeramicCache
from django.test import Client
from pytest_bdd import given, scenario, then, when


pytestmark = pytest.mark.django_db


@scenario("features/submit_stamp.feature", "Submit valid VC from passport")
def test_submit_valid_vc_from_passport():
    """Submit valid VC from passport."""


@given("I am a user that claims a stamp with our IAM server")
def _():
    """I am a user that claims a stamp with our IAM server."""
    pass


@when(
    "the IAM server validates the conditions and creates the Stamp (VerifiedCredential)"
)
def _(verifiable_credential, sample_provider, sample_address):
    """the IAM server validates the conditions and creates the Stamp (VerifiedCredential)."""
    pass


@then(
    "it stores the stamp in the DB Cache by posting it to the Scorer API URL",
    target_fixture="cache_stamp_response",
)
def _(verifiable_credential, sample_provider, sample_address, sample_token):
    """it stores the stamp in the DB Cache by posting it to the Scorer API URL."""
    params = {
        "address": sample_address,
        "provider": sample_provider,
        "stamp": verifiable_credential,
    }

    client = Client()
    cache_stamp_response = client.post(
        "/ceramic-cache/stamp",
        json.dumps(params),
        content_type="application/json",
        **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
    )

    assert cache_stamp_response.status_code == 201
    assert CeramicCache.objects.filter(
        address=sample_address, provider=sample_provider
    ).exists()

    return cache_stamp_response


@then("then it returns it to the Passport app")
def _(cache_stamp_response, verifiable_credential, sample_provider, sample_address):
    assert cache_stamp_response.status_code == 201
    assert cache_stamp_response.json() == {
        "address": sample_address,
        "provider": sample_provider,
        "stamp": verifiable_credential,
    }
