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


@scenario("features/submit_passport.feature", "Submit passport successfully")
def test_submit_passport_successfully():
    """Submit passport successfully."""


@given(
    "that I'm a Passport developer and have a community ID", target_fixture="community"
)
def _():
    """that I'm a Passport developer and have a community ID."""
    user = User.objects.create_user(username="testuser-1", password="12345")

    # TODO: load mnemonic from env
    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    account = Account.objects.create(user=user, address=web3_account.address)

    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=account,
    )

    print(user)
    return community


@when("I call the submit-passport API for a specific ETH address")
def _(community, mocker):
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
        "community": community.id,
        "address": community.account.address,
        "signature": signed_message.signature.hex(),
    }

    response = client.post(
        "/registry/submit-passport",
        json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200


@then(
    "the API logs all of the valid Passport data points (VCs), namely the complete JSON, mapped to that Passport holder within the respective community ID directory"
)
def _(community):
    """the API logs all of the valid Passport data points (VCs), namely the complete JSON, mapped to that Passport holder within the respective community ID directory."""
    assert len(Passport.objects.all()) == 1
    passport = Passport.objects.all()[0]

    assert passport.community.id == community.id


@then("the API reads all of the Passport data points")
def _():
    """the API reads all of the Passport data points."""
    pass
