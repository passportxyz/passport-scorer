"""Create API keys feature tests."""
import json

import pytest
from account.models import Account, AccountAPIKey
from account.test.test_api_key import mock_api_key_body
from django.contrib.auth.models import User
from django.test import Client
from eth_account.messages import encode_defunct
from ninja_jwt.schema import RefreshToken
from pytest_bdd import given, scenario, then, when
from registry.test.test_passport_submission import mock_passport
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

    mocker.patch("account.views.create_api_key", return_value=mock_api_key_body)
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
def _(scorer_api_key, scorer_community_with_gitcoin_default, mocker):
    """I can use that key to call the API."""

    mocker.patch("registry.api.get_passport", return_value=mock_passport)
    mocker.patch("registry.api.validate_credential", side_effect=[[], []])

    client = Client()

    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    signed_message = web3.eth.account.sign_message(
        encode_defunct(text="I authorize the passport scorer to validate my account"),
        private_key=web3_account.key,
    )

    payload = {
        "community": scorer_community_with_gitcoin_default.id,
        "address": scorer_community_with_gitcoin_default.account.address,
        "signature": signed_message.signature.hex(),
    }

    response = client.post(
        "/api/registry/submit-passport",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
    )

    assert response.status_code == 200
    return response
