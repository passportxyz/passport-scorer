import binascii
import json
from django.test import TestCase
from django.test import Client
from account.models import Community, Account
from django.contrib.auth.models import User
from web3 import Web3
from eth_account.messages import encode_defunct
from registry.utils import get_signer, verify_issuer, verify_expiration
from unittest.mock import patch
from datetime import datetime, timedelta

from registry.models import Passport, Stamp

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()


ens_credential = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..b_ek317zi0Gq3SylrtJeODlbZuRrzfv-1TTBBNcBrDTMDBTikzPJMR2A1SuVcrfUl3MpNZ-zymaLGB5qz9xdDg",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:22.279Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).isoformat(),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:xG1Todke+0P1jphcnZhP/3UA5XUBMaEux4fHG86I20U=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Ens",
    },
}

ens_credential_corrupted = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..b_ek317zi0Gq3SylrtJeODlbZuRrzfv-1TTBBNcBrDTMDBTikzPJMR2A1SuVcrfUl3MpNZ-zymaLGB5qz9xdDg",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:22.279Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC"
        + "CORRUPTING THE FIELD",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).isoformat(),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:xG1Todke+0P1jphcnZhP/3UA5XUBMaEux4fHG86I20U=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Ens",
    },
}


google_credential = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..UvANt5nz16WNjkGTyUFIxbMBmYdEFZcVrD97L3EzOkvxz8eN-6UKeFZul_uPBfa88h50jKQgVgJlJqxR8kpSAQ",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:04.698Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).isoformat(),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:edgFWHsCSaqGxtHSqdiPpEXR06Ejw+YLO9K0BSjz0d8=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Google",
    },
}


google_credential_expired = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..UvANt5nz16WNjkGTyUFIxbMBmYdEFZcVrD97L3EzOkvxz8eN-6UKeFZul_uPBfa88h50jKQgVgJlJqxR8kpSAQ",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:04.698Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=30)).isoformat(),
    "expirationDate": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:edgFWHsCSaqGxtHSqdiPpEXR06Ejw+YLO9K0BSjz0d8=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Google",
    },
}

mock_passport = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expiryDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential},
        {"provider": "Ens", "credential": ens_credential},
    ],
}

mock_passport_with_corrupted_stamp = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expiryDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential},
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Ens", "credential": ens_credential_corrupted},
    ],
}


mock_passport_with_expired_stamp = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expiryDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential},
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Ens", "credential": google_credential_expired},
    ],
}


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

        self.user_account = Account.objects.create(
            user=self.user, address=account.address
        )

        self.community = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=self.user_account,
        )

        self.signed_message = web3.eth.account.sign_message(
            encode_defunct(
                text="I authorize the passport scorer to validate my account"
            ),
            private_key=self.account.key,
        )

        self.client = Client()

    def test_verify_signature(self):
        signer = get_signer(self.signed_message.signature.hex())
        self.assertEqual(signer, self.account.address)

    def test_verify_signature_wrong_signature(self):
        # Change the signature
        signature = bytearray(self.signed_message.signature)
        signature[0] = signature[0] + 1
        signature = bytes(signature)

        signer = get_signer(signature)
        self.assertNotEqual(signer, self.account.address)

    def test_invalid_address_throws_exception(self):
        payload = {
            "address": "0x0",
            "signature": self.signed_message.signature.hex(),
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_valid_issuer(self):
        valid = verify_issuer(mock_passport)
        self.assertEqual(valid, True)

    # TODO: Check requirements for stamp expiration - i.e. does one expired stamp invalidate a passport
    # def test_passport_expiration_dates(self):
    #     valid = verify_expiration(mock_passport)
    #     self.assertEqual(valid, True)

    @patch("registry.views.get_passport", return_value=mock_passport)
    def test_submit_passport(self, get_passport):
        # get_passport.return_value = mock_passport

        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].passport, mock_passport)
        self.assertEqual(all_passports[0].did, did)
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch("registry.views.get_passport", return_value=mock_passport)
    def test_submit_passport_missing_community(self, get_passport):
        """
        Make sure that the community is required when submitting eth address
        """
        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 0)

    @patch(
        "registry.views.get_passport",
        return_value=mock_passport_with_corrupted_stamp,
    )
    def test_submit_passport_with_invalid_stamp(self, get_passport):
        """
        Verify that stamps wich do not pass te didkit validation are ignored and not stored in the DB
        """
        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].passport, mock_passport_with_corrupted_stamp)
        self.assertEqual(all_passports[0].did, did)
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch(
        "registry.views.get_passport",
        return_value=mock_passport_with_expired_stamp,
    )
    def test_submit_passport_with_expired_stamps(self, get_passport):
        """
        Verify that stamps that are expired are ignored
        """
        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].passport, mock_passport_with_expired_stamp)
        self.assertEqual(all_passports[0].did, did)
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )
