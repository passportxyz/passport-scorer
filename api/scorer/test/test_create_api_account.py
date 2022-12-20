"""Create an API account feature tests."""

import binascii
import json
from copy import deepcopy
from datetime import datetime

import pytest
from account.models import Account
from django.test import Client
from eth_account.messages import encode_defunct
from pytest_bdd import given, scenario, then, when
from siwe import SiweMessage
from web3 import Web3
from web3.auto import w3

pytestmark = pytest.mark.django_db

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

nonce = "97608e7f0a35c04a47f56999dbaa02174a6acf88b0fd422e8b148feb20721f6c"


@scenario("features/create_api_account.feature", "Successfully create an API account")
def test_successfully_create_an_api_account():
    """Successfully create an API account."""


@given(
    "that I am a builder and I don't have an API ACCOUNT",
    target_fixture="no_account_db_response",
)
def _(no_account_db_response):
    """that I am a builder and I don't have an API ACCOUNT."""
    # User's address is not in the database --> so they need to:
    return no_account_db_response


@when("I hit the Connect Wallet button")
def _(mocker):
    """I hit the Connect Wallet button."""

    mocker.patch("account.views.nonce", return_value=nonce)


@then("I Sign-in-with-Ethereum", target_fixture="account_response")
def _():
    """I Sign-in-with-Ethereum."""

    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    c = Client()
    response = c.get("/account/nonce")

    data = response.json()

    siwe_data = {
        "domain": "localhost",
        "address": account.address,
        "statement": "Sign in with Ethereum to the app.",
        "uri": "http://localhost/",
        "version": "1",
        "chainId": "1",
        "nonce": data["nonce"],
        "issuedAt": datetime.utcnow().isoformat(),
    }

    siwe_data_pay = deepcopy(siwe_data)
    siwe_data_pay["chain_id"] = siwe_data_pay["chainId"]
    siwe_data_pay["issued_at"] = siwe_data_pay["issuedAt"]

    siwe = SiweMessage(siwe_data_pay)
    data_to_sign = siwe.prepare_message()

    private_key = account.key
    signed_message = w3.eth.account.sign_message(
        encode_defunct(text=data_to_sign), private_key=private_key
    )

    account_response = c.post(
        "/account/verify",
        json.dumps(
            {
                "message": siwe_data,
                "signature": binascii.hexlify(signed_message.signature).decode("utf-8"),
            }
        ),
        content_type="application/json",
    )

    return account_response


@then("I will have an account created", target_fixture="account_response")
def _(account_response):
    """I will have an account created."""

    assert account_response.status_code == 200
    assert len(Account.objects.all()) == 1


@then("be taken to the dashboard")
def _():
    """be taken to the dashboard."""
    pass
