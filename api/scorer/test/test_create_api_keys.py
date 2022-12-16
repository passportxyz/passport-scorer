"""Create API keys feature tests."""
import json

import pytest
from account.models import AccountAPIKey
from account.test.test_api_key import mock_api_key_body
from django.test import Client
from ninja_jwt.schema import RefreshToken
from pytest_bdd import given, scenario, then, when
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

pytestmark = pytest.mark.django_db


@scenario(
    "features/create_api_keys.feature", "Successfully create API keys for my apps"
)
def test_successfully_create_api_keys_for_my_apps():
    """Successfully create up to the maximum API keys for my apps."""


@given("that I have an API account", target_fixture="account")
def _(scorer_account, mocker):
    """that I have an API account."""

    mocker.patch("account.views.submit_signed_challenge", return_value=scorer_account)


@when("I hit the Create API key button")
def _(scorer_user, mocker):
    """I hit the Create API key button."""

    refresh = RefreshToken.for_user(scorer_user)
    access_token = refresh.access_token

    client = Client()

    api_key_response = client.post(
        "/account/api-key",
        json.dumps(mock_api_key_body),
        content_type="application/json",
        **{"HTTP_AUTHORIZATION": f"Bearer {access_token}"},
    )

    assert api_key_response.status_code == 200

    # Check that the API key was created
    all_api_keys = list(AccountAPIKey.objects.all())
    assert len(all_api_keys) == 1

    return api_key_response


@then("I’m returned a secret API key, basically a long cryptic string")
def _():
    """I’m returned a secret API key, basically a long cryptic string."""
    # Implemented in the previous step
    pass


@then("I can use that key to call the API")
def _(scorer_api_key, scorer_community_with_gitcoin_default):
    """I can use that key to call the API."""

    client = Client()

    response = client.get(
        f"/api/registry/score/{scorer_community_with_gitcoin_default.id}/{scorer_community_with_gitcoin_default.account.address}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
    )

    assert response.status_code == 200
    assert response.json() == {
        "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
        "score": "1001234.000000000",
    }
