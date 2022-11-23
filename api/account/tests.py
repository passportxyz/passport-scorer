from django.test import TestCase
from django.test import Client

# Create your tests here.
from .models import Account

from web3.auto import w3
from web3 import Web3
from eth_account.messages import encode_defunct
import binascii
import json


class AccountTestCase(TestCase):
    def setUp(self):
        pass

    def test_create_account_with_SIWE(self):
        """Test creation of an account wit SIWE"""
        web3 = Web3()
        web3.eth.account.enable_unaudited_hdwallet_features()
        # TODO: load mnemonic fomr env
        my_mnemonic = (
            "chief loud snack trend chief net field husband vote message decide replace"
        )
        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        print("account", account.address)

        c = Client()
        response = c.get("/account/challenge?address={account.address}")
        self.assertEqual(200, response.status_code)

        data = response.json()
        # TODO: verify data

        private_key = account.key
        message = encode_defunct(text=data["statement"])
        signed_message = w3.eth.account.sign_message(message, private_key=private_key)

        response = c.post(
            "/account/submit_signed_challenge",  # submit_signed_challenge",
            json.dumps(
                {
                    "address": account.address,
                    "signature": binascii.hexlify(signed_message.signature).decode(
                        "utf-8"
                    ),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        print("response:", data)
        self.assertTrue("refresh" in data)
        self.assertTrue("access" in data)


