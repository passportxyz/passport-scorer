import binascii
from django.test import TestCase
from django.test import Client
from account.models import Community, Account
from django.contrib.auth.models import User
from web3 import Web3
from eth_account.messages import encode_defunct
from registry.utils import verify_signature


web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

class ValidatePassportTestCase(TestCase):
    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        self.user = User.objects.create_user(username="admin", password="12345")

        
        # TODO: load mnemonic from env
        my_mnemonic = (
            "chief loud snack trend chief net field husband vote message decide replace"
        )
        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        self.account = account

        self.user_account = Account.objects.create(user=self.user, address=account.address)

    def test_verify_signature(self):
        signed_message = web3.eth.account.sign_message(
            encode_defunct(text="I authorize the passport scorer to validate my account"), private_key=self.account.key
        )

        signer = verify_signature(signed_message.signature)
        self.assertEqual(signer, self.account.address)

    def test_verify_signature_wrong_signature(self):
        signed_message = web3.eth.account.sign_message(
            encode_defunct(text="I authorize the passport scorer to validate my account"), private_key=self.account.key
        )

        # Change the signature
        signature = bytearray(signed_message.signature)
        signature[0] = signature[0] + 1
        signature = bytes(signature)

        signer = verify_signature(signature)
        self.assertNotEqual(signer, self.account.address)

    def test_verify_working(self):
        c = Client()
        response = c.get("/registry/submit-passport")
        self.assertEqual(response.status_code, 200)
