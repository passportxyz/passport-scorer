from unittest.mock import patch

from account.models import Account, AccountAPIKey
from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase
from web3 import Web3
from django.conf import settings

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC


class SigningMessageTestCase(TransactionTestCase):
    def setUp(self):
        self.client = Client()

        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )

        self.account = account

        self.user = User.objects.create_user(username="admin", password="12345")
        self.user_account = Account.objects.create(
            user=self.user, address=account.address
        )
        (account_api_key, secret) = AccountAPIKey.objects.create_key(
            account=self.user_account, name="Token for user 1"
        )
        self.account_api_key = account_api_key
        self.secret = secret

    def test_get_signing_message(self):

        response = self.client.get(
            "/registry/signing-message",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue("message" in response.json())
        self.assertTrue("nonce" in response.json())
