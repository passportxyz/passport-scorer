"""Create an API account feature tests."""

import binascii
import json
from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

import pytest
from account.models import Account, Nonce
from django.conf import settings
from django.test import Client
from eth_account.messages import encode_defunct
from pytest_bdd import given, scenario, then, when
from siwe import SiweMessage
from web3 import Web3
from web3.auto import w3

pytestmark = pytest.mark.django_db

my_mnemonic = settings.TEST_MNEMONIC
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

nonce = "97608e7f0a35c04a47f56999dbaa02174a6acf88b0fd422e8b148feb20721f6c"


@scenario("features/create_api_account.feature", "Successfully create an API account")
def test_successfully_create_an_api_account():
    """Successfully create an API account."""


@given("that I am a builder and I don't have an API ACCOUNT")
def _():
    """that I am a builder and I don't have an API ACCOUNT."""


@when("I hit the Connect Wallet button")
def _():
    """I hit the Connect Wallet button."""


@then("I Sign-in-with-Ethereum", target_fixture="account_response")
def _():
    """I Sign-in-with-Ethereum."""

    account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    c = Client()
    response = c.get("/account/nonce")

    data = response.json()
    nonce = data["nonce"]

    siwe_data = {
        "domain": "localhost:3000",
        "address": account.address,
        "statement": f"Welcome to Gitcoin Passport Scorer! This request will not trigger a blockchain transaction or cost any gas fees. Your authentication status will reset in 24 hours. Wallet Address: ${account.address}. Nonce: ${nonce}",
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


@then("I will have an account created")
def _(account_response, scorer_account):
    """I will have an account created."""
    account = Account.objects.all()[0]
    assert account.address == scorer_account.address.lower()
    assert account_response.status_code == 200


@then("be taken to the dashboard")
def _():
    """be taken to the dashboard."""
    pass


@scenario("features/create_api_account.feature", "Invalid Nonce useage")
def test_invalid_nonce_useage():
    """Invalid Nonce useage."""


@given(
    "that I have an expired nonce",
    target_fixture="badNonceVerifyPayload",
)
def _(mocker):
    """that I have an expired nonce""",

    account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    c = Client()

    expiredNonce = Nonce.create_nonce(ttl=-10)

    with patch(
        "account.models.Nonce.create_nonce", return_value=expiredNonce
    ) as nonceMock:
        response = c.get("/account/nonce")
        nonceMock.assert_called()

    data = response.json()
    nonce = data["nonce"]

    siwe_data = {
        "domain": "localhost",
        "address": account.address,
        "statement": f"Welcome to Gitcoin Passport Scorer! This request will not trigger a blockchain transaction or cost any gas fees. Your authentication status will reset in 24 hours. Wallet Address: ${account.address}. Nonce: ${nonce}",
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

    return json.dumps(
        {
            "message": siwe_data,
            "signature": binascii.hexlify(signed_message.signature).decode("utf-8"),
        }
    )


@when("I verify the SIWE message", target_fixture="badNonceVerifyResponse")
def _(badNonceVerifyPayload):
    c = Client()
    return c.post(
        "/account/verify",
        badNonceVerifyPayload,
        content_type="application/json",
    )


@then("verification fails")
def _(badNonceVerifyResponse):
    assert badNonceVerifyResponse.status_code == 400
