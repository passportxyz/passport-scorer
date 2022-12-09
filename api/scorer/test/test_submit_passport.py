"""Submit address for passport feature tests."""

import pytest
from account.models import Account, AccountAPIKey, Community
from registry.models import Passport, Stamp
from django.contrib.auth.models import User
from django.test import Client
from web3 import Web3
from eth_account.messages import encode_defunct
import json

from registry.test.test_passport_submission import mock_passport
from unittest.mock import patch

from pytest_bdd import (
    given,
    scenario,
    then,
    when,
)

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

pytestmark = pytest.mark.django_db


@pytest.fixture
def scorer_user():
    user = User.objects.create_user(username="testuser-1", password="12345")
    print("scorer_user user", user)
    return user


@pytest.fixture
def scorer_account(scorer_user):
    # TODO: load mnemonic from env
    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    print("scorer_user", scorer_user)
    print("web3_account.address", web3_account.address)
    account = Account.objects.create(user=scorer_user, address=web3_account.address)
    return account


@pytest.fixture
def scorer_api_key(scorer_account):
    (account_api_key, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account, name="Token for user 1"
    )
    return secret


@pytest.fixture
def scorer_community(scorer_account):
    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=scorer_account,
    )
    return community


@scenario("features/submit_passport.feature", "Submit passport successfully")
def test_submit_passport_successfully():
    """Submit passport successfully."""


@given(
    "that I'm a Passport developer and have a community ID", target_fixture="community"
)
def _(scorer_community):
    """that I'm a Passport developer and have a community ID."""
    pass


@when("I call the submit-passport API for a specific ETH address")
def _(scorer_api_key, scorer_community, mocker):
    """I call the submit-passport API for a specific ETH address."""
    mocker.patch("registry.views.get_passport", return_value=mock_passport)
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
        "community": scorer_community.id,
        "address": scorer_community.account.address,
        "signature": signed_message.signature.hex(),
    }

    response = client.post(
        "/registry/submit-passport",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
    )

    assert response.status_code == 200


@then(
    "the API logs all of the valid Passport data points (VCs), namely the complete JSON, mapped to that Passport holder within the respective community ID directory"
)
def _(scorer_community):
    """the API logs all of the valid Passport data points (VCs), namely the complete JSON, mapped to that Passport holder within the respective community ID directory."""
    assert len(Passport.objects.all()) == 1
    passport = Passport.objects.all()[0]

    assert passport.community.id == scorer_community.id


@then("the API reads all of the Passport data points")
def _():
    """the API reads all of the Passport data points."""
    pass
