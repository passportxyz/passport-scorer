import binascii
import json
from copy import deepcopy
from datetime import datetime

from account.models import Account
from django.conf import settings
from django.test import Client, TestCase
from eth_account.messages import encode_defunct
from siwe import SiweMessage
from web3 import Web3
from web3.auto import w3

my_mnemonic = settings.TEST_MNEMONIC

# Create your tests here.


mock_api_key_body = {"name": "test"}
mock_community_body = {"name": "test", "description": "test"}


web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
account = web3.eth.account.from_mnemonic(my_mnemonic, account_path="m/44'/60'/0'/0/0")

c = Client()


class AccountTestCase(TestCase):
    def setUp(self):
        response = c.get("/account/nonce")
        nonce = response.json()["nonce"]

        siwe_data = {
            "domain": "localhost:3000",
            "address": account.address,
            "statement": f"Welcome to Gitcoin Passport Scorer! This request will not trigger a blockchain transaction or cost any gas fees. Your authentication status will reset in 24 hours. Wallet Address: ${account.address}. Nonce: ${nonce}",
            "uri": "http://localhost/",
            "version": "1",
            "chainId": "1",
            "nonce": nonce,
            "issuedAt": datetime.utcnow().isoformat(),
        }

        self.siwe_data = siwe_data

        siwe_data_pay = deepcopy(siwe_data)
        siwe_data_pay["chain_id"] = siwe_data_pay["chainId"]
        siwe_data_pay["issued_at"] = siwe_data_pay["issuedAt"]
        self.siwe_data_pay = siwe_data_pay

    def test_nonce(self):
        """Test that nonce endpoint works"""
        response = c.get("/account/nonce")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertTrue("nonce" in data)

    def test_create_account_with_SIWE(self):
        """Test creation of an account wit SIWE"""
        siwe = SiweMessage(self.siwe_data_pay)
        data_to_sign = siwe.prepare_message()

        private_key = account.key
        signed_message = w3.eth.account.sign_message(
            encode_defunct(text=data_to_sign), private_key=private_key
        )

        response = c.post(
            "/account/verify",
            json.dumps(
                {
                    "message": self.siwe_data,
                    "signature": binascii.hexlify(signed_message.signature).decode(
                        "utf-8"
                    ),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        # Refresh/access JWT created by django
        self.assertTrue("refresh" in data)
        self.assertTrue("access" in data)

    def test_account_address_is_lower_case(self):
        siwe = SiweMessage(self.siwe_data_pay)
        data_to_sign = siwe.prepare_message()

        private_key = account.key
        signed_message = w3.eth.account.sign_message(
            encode_defunct(text=data_to_sign), private_key=private_key
        )

        response = c.post(
            "/account/verify",
            json.dumps(
                {
                    "message": self.siwe_data,
                    "signature": binascii.hexlify(signed_message.signature).decode(
                        "utf-8"
                    ),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        created_account = Account.objects.get(address=account.address.lower())
        self.assertEqual(created_account.address, account.address.lower())

    def test_create_account_with_www_domain(self):
        siwe = SiweMessage(self.siwe_data_pay)
        data_to_sign = siwe.prepare_message()
        data_to_sign = siwe.prepare_message()

        private_key = account.key
        signed_message = w3.eth.account.sign_message(
            encode_defunct(text=data_to_sign), private_key=private_key
        )

        response = c.post(
            "/account/verify",
            json.dumps(
                {
                    "message": self.siwe_data,
                    "signature": binascii.hexlify(signed_message.signature).decode(
                        "utf-8"
                    ),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        # Refresh/access JWT created by django
        self.assertTrue("refresh" in data)
        self.assertTrue("access" in data)
