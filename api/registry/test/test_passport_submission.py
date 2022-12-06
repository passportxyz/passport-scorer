import binascii
from django.test import TestCase
from django.test import Client
from account.models import Community, Account
from django.contrib.auth.models import User
from web3 import Web3
from eth_account.messages import encode_defunct
from registry.views import verify_signature


class ValidatePassportTestCase(TestCase):
    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        self.user = User.objects.create_user(username="admin", password="12345")

        web3 = Web3()
        web3.eth.account.enable_unaudited_hdwallet_features()
        # TODO: load mnemonic from env
        my_mnemonic = (
            "chief loud snack trend chief net field husband vote message decide replace"
        )
        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )


        self.account = Account.objects.create(user=self.user, address=account.address)

        signed_message = web3.eth.account.sign_message(
            encode_defunct(text="I authorize the passport scorer to validate my account"), private_key=account.key
        )

        self.signed_message = signed_message

    def test_verify_signature(self):
        signer = verify_signature(self.signed_message.signature)

        self.assertEqual(signer, self.account.address)
