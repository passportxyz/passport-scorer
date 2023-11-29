import copy
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from account.deduplication import Rules
from account.models import Account, AccountAPIKey, Community, Nonce
from ceramic_cache.models import CeramicCache
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase
from eth_account.messages import encode_defunct
from registry.models import Passport, Stamp
from registry.tasks import score_passport
from registry.utils import get_signer, get_signing_message, verify_issuer
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

my_mnemonic = settings.TEST_MNEMONIC

ens_credential = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..b_ek317zi0Gq3SylrtJeODlbZuRrzfv-1TTBBNcBrDTMDBTikzPJMR2A1SuVcrfUl3MpNZ-zymaLGB5qz9xdDg",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:22.279Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": settings.TRUSTED_IAM_ISSUER,
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
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
    "issuer": settings.TRUSTED_IAM_ISSUER,
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
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
    "issuer": settings.TRUSTED_IAM_ISSUER,
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
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


google_credential_2 = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..UvANt5nz16WNjkGTyUFIxbMBmYdEFZcVrD97L3EzOkvxz8eN-6UKeFZul_uPBfa88h50jKQgVgJlJqxR8kpSAQ",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:04.698Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": settings.TRUSTED_IAM_ISSUER,
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:edgFWHsCSaqGxthSqdilpEXR06Ojw+YLO8K0BSjz0d8=",
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
    "issuer": settings.TRUSTED_IAM_ISSUER,
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
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

google_credential_soon_to_be_expired = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..UvANt5nz16WNjkGTyUFIxbMBmYdEFZcVrD97L3EzOkvxz8eN-6UKeFZul_uPBfa88h50jKQgVgJlJqxR8kpSAQ",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:04.698Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": settings.TRUSTED_IAM_ISSUER,
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=27)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
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

mock_utc_timestamp = datetime(2015, 2, 1, 15, 16, 17, 345, tzinfo=timezone.utc)

mock_passport = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Google", "credential": google_credential},
    ],
}

mock_passport_2 = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Google", "credential": google_credential_2},
    ],
}

mock_passport_google = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential_2},
    ],
}

mock_passport_with_corrupted_stamp = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential},
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Ens", "credential": ens_credential_corrupted},
    ],
}


mock_passport_with_expired_stamp = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential},
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Ens", "credential": google_credential_expired},
    ],
}

mock_passport_with_soon_to_be_expired_stamp = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential_soon_to_be_expired},
    ],
}


class ValidatePassportTestCase(TransactionTestCase):
    base_url = "/registry"

    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        self.user = User.objects.create_user(username="admin", password="12345")

        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        account_2 = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )

        self.account = account
        self.account_2 = account_2

        self.user_account = Account.objects.create(
            user=self.user, address=account.address
        )

        # Mock the default weights for new communities that are created
        with patch(
            "scorer_weighted.models.settings.GITCOIN_PASSPORT_WEIGHTS",
            {
                "Google": 1,
                "Ens": 1,
            },
        ):
            self.community = Community.objects.create(
                name="My Community",
                description="My Community description",
                account=self.user_account,
            )

        self.nonce = Nonce.create_nonce().nonce
        self.nonce_2 = Nonce.create_nonce().nonce

        self.signing_message = get_signing_message(self.nonce)
        self.signing_message_2 = get_signing_message(self.nonce_2)

        self.signed_message = web3.eth.account.sign_message(
            encode_defunct(text=self.signing_message),
            private_key=self.account.key,
        )
        self.signed_message_2 = web3.eth.account.sign_message(
            encode_defunct(text=self.signing_message),
            private_key=self.account_2.key,
        )

        self.user2 = User.objects.create_user(username="admin2", password="12345")
        self.user_account2 = Account.objects.create(user=self.user2, address="0x02")
        self.community2 = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=self.user_account2,
        )

        (account_api_key, secret) = AccountAPIKey.objects.create_key(
            account=self.user_account,
            name="Token for user 1",
        )
        self.account_api_key = account_api_key
        self.secret = secret

        mock_mnemonic = "tourist search plug company mail blind arch rather angry captain spin reform"
        mock_account = web3.eth.account.from_mnemonic(
            mock_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        self.mock_account = mock_account
        self.mock_signed_message = web3.eth.account.sign_message(
            encode_defunct(text=self.signing_message),
            private_key=self.mock_account.key,
        )

        self.client = Client()

    def test_invalid_api_key(self):
        payload = {
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "community": self.community.id,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Token 1234",
        )

        self.assertEqual(response.status_code, 401)

    def test_verify_signature(self):
        signer = get_signer(self.nonce, self.signed_message.signature.hex())
        self.assertEqual(signer, self.account.address)

    def test_verify_signature_wrong_signature(self):
        """Compare signature of account_2 against account"""
        # Change the signature
        signature = bytearray(self.signed_message_2.signature)
        signature[0] = signature[0]
        signature = bytes(signature)

        signer = get_signer(self.nonce_2, signature)
        self.assertNotEqual(signer, self.account.address)

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    def test_signature_not_needed_by_default(self, aget_passport, validate_credential):
        payload = {
            "community": self.community.id,
            "address": self.account.address,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/json",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_valid_issuer(self):
        valid = verify_issuer(mock_passport["stamps"][1])
        self.assertEqual(valid, True)

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    def test_submit_passport_saves_analyitcs(self, aget_passport, validate_credential):
        # get_passport.return_value = mock_passport
        settings.FF_API_ANALYTICS = "on"

        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/json",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)

        prefix, _, _ = self.secret.partition(".")
        queryset = AccountAPIKey.objects.get_usable_keys()
        assert (queryset.get(prefix=prefix)).id == self.account_api_key.id

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    def test_submit_passport(self, aget_passport, validate_credential):
        # get_passport.return_value = mock_passport

        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/json",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)

        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(len(all_passports[0].stamps.all()), 2)

        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    def test_submitted_passport_has_lower_case_address_value(
        self, aget_passport, validate_credential
    ):
        payload = {
            "community": self.community.pk,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/json",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )

        self.assertEqual(response.status_code, 200)

        created_passport = Passport.objects.get(address=self.account.address.lower())
        self.assertEqual(created_passport.address, self.account.address.lower())

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    def test_submit_passport_reused_nonce(self, aget_passport, validate_credential):
        """Test that submitting a reused nonce results in rejection"""

        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        for _ in [1, 2]:
            response = self.client.post(
                f"{self.base_url}/submit-passport",
                json.dumps(payload),
                **{
                    "content_type": "application/json",
                    "HTTP_AUTHORIZATION": f"Token {self.secret}",
                },
            )

        self.assertEqual(response.json(), {"detail": "Invalid nonce."})
        self.assertEqual(response.status_code, 400)

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value={},
    )
    def test_submitting_without_passport(self, aget_passport, validate_credential):
        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/json",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        # We do expect an empty passport to have been stored
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].stamps.count(), 0)

        response = self.client.get(
            f"{self.base_url}/score/{self.community.id}/{self.account.address}",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )

        assert response.status_code == 200
        assert response.json() == {
            "address": self.account.address.lower(),
            "score": None,
            "evidence": None,
            "last_score_timestamp": None,
            "status": "ERROR",
            "error": "No Passport found for this address.",
            "stamp_scores": {},
        }

    @patch("registry.atasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.atasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    def test_submit_passport_multiple_times(
        self, _, aget_passport, validate_credential
    ):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""
        # get_passport.return_value = mock_passport

        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        expectedResponse = {
            "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
            "evidence": None,
            "last_score_timestamp": "2023-01-11T16:35:23.938006+00:00",
            "score": Decimal("2.000000000"),
            "status": "DONE",
            "error": None,
            "stamp_scores": {"Ens": 1.0, "Google": 1.0},
        }

        expected2ndResponse = {
            "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
            "evidence": None,
            "last_score_timestamp": "2023-01-11T16:35:23.938006+00:00",
            "score": Decimal("2.000000000"),
            "status": "DONE",
            "error": None,
            "stamp_scores": {"Ens": 1.0, "Google": 1.0},
        }

        # First submission
        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/tson",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        response_json["score"] = Decimal(response_json["score"])
        self.assertEqual(
            response_json,
            expectedResponse,
        )

        # 2nd submission
        # Get another nonce (nonces can only be used once)
        nonce = Nonce.create_nonce().nonce
        signing_message = get_signing_message(nonce)
        signed_message = web3.eth.account.sign_message(
            encode_defunct(text=signing_message),
            private_key=self.account_2.key,
        )

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": signed_message.signature.hex(),
            "nonce": nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/tson",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        response_json["score"] = Decimal(response_json["score"])
        self.assertEqual(
            response_json,
            expected2ndResponse,
        )

        # Check that the stamps have only been recorded once
        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)

        self.assertEqual(all_passports[0].stamps.count(), len(mock_passport["stamps"]))
        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    def test_submit_passport_missing_community_and_scorer_id(self):
        """
        Make sure that the community is required when submitting eth address
        """
        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 422)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 0)

    def test_submit_passport_accepts_scorer_id(self):
        """
        Make sure that the scorer_id is an acceptable parameter
        """

        payload = {
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
            "scorer_id": self.community.pk,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)

    @patch(
        "registry.atasks.validate_credential",
        side_effect=[[], [], ["Stamp validation failed: invalid date"]],
    )
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport_with_corrupted_stamp,
    )
    def test_submit_passport_with_invalid_stamp(
        self, aget_passport, validate_credential
    ):
        """
        Verify that stamps which do not pass the didkit validation are ignored and not stored in the DB
        """

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)

        self.assertEqual(
            all_passports[0].stamps.all()[0].credential,
            mock_passport_with_corrupted_stamp["stamps"][0]["credential"],
        )

        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport_with_expired_stamp,
    )
    def test_submit_passport_with_expired_stamps(
        self, aget_passport, validate_credential
    ):
        """
        Verify that stamps that are expired are ignored
        """

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    def test_that_community_is_associated_with_passport(
        self, aget_passport, validate_credential
    ):
        """
        Verify that the community is associated with the passport
        """

        payload = {
            "community": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        self.assertEqual(
            all_passports[0].stamps.all()[0].credential,
            mock_passport["stamps"][0]["credential"],
        )
        self.assertEqual(
            all_passports[0].stamps.all()[1].credential,
            mock_passport["stamps"][1]["credential"],
        )
        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(all_passports[0].community, self.community)

    def test_that_only_owned_communities_can_submit_passport(self):
        """
        Verify that only communities owned by the user of the API key can create passports
        """

        payload = {
            "community": self.community2.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 404)

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport_google,
    )
    def test_lifo_deduplication_duplicate_stamps(
        self, aget_passport, validate_credential
    ):
        """
        Test the successful deduplication of stamps by last in first out (LIFO)
        """

        address_1 = self.account.address.lower()
        submission_address = self.mock_account.address.lower()

        # Create first passport
        first_passport = Passport.objects.create(
            address=address_1,
            community=self.community,
        )

        Stamp.objects.create(
            passport=first_passport,
            hash=ens_credential["credentialSubject"]["hash"],
            provider="Ens",
            credential=ens_credential,
        )

        Stamp.objects.create(
            passport=first_passport,
            hash=google_credential["credentialSubject"]["hash"],
            provider="Google",
            credential=google_credential,
        )

        # Now we submit a duplicate hash, and expect deduplication to happen
        submission_test_payload = {
            "community": self.community.id,
            "address": self.mock_account.address,
            "signature": self.mock_signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        submission_response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(submission_test_payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )

        self.assertEqual(submission_response.status_code, 200)

        updated_passport = Passport.objects.get(address=submission_address)

        self.assertEqual(updated_passport.stamps.count(), 1)
        self.assertEqual(updated_passport.address, submission_address)
        self.assertEqual(updated_passport.stamps.all()[0].provider, "Google")

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport_google,
    )
    def test_fifo_deduplication_duplicate_stamps(
        self, aget_passport, validate_credential
    ):
        """
        Test the successful deduplication of stamps by first in first out (FIFO)
        """
        address_1 = self.account.address
        address_2 = self.mock_account.address

        fifo_community = Community.objects.create(
            name="My FIFO Community",
            description="My FIFO Community description",
            account=self.user_account,
            rule=Rules.FIFO.value,
        )

        # Create first passport
        first_passport = Passport.objects.create(
            address=address_1.lower(),
            community=fifo_community,
            requires_calculation=True,
        )

        Stamp.objects.create(
            passport=first_passport,
            hash=ens_credential["credentialSubject"]["hash"],
            provider="Ens",
            credential=ens_credential,
        )

        # Create existing stamp that is a duplicate of the one we are going to submit
        Stamp.objects.create(
            passport=first_passport,
            hash=google_credential_2["credentialSubject"]["hash"],
            provider="Google",
            credential=google_credential_2,
        )

        # Now we submit a duplicate hash, and expect deduplication to happen
        submission_test_payload = {
            "community": fifo_community.pk,
            "address": address_2,
            "nonce": self.nonce,
        }

        submission_response = self.client.post(
            f"{self.base_url}/submit-passport",
            json.dumps(submission_test_payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )

        self.assertEqual(submission_response.status_code, 200)

        # first_passport should have just one stamp and the google stamps should be deleted
        deduped_first_passport = Passport.objects.get(address=address_1)

        self.assertEqual(deduped_first_passport.stamps.count(), 1)
        self.assertEqual(deduped_first_passport.stamps.all()[0].provider, "Ens")

        # assert submitted passport contains the google stamp
        submitted_passport = Passport.objects.get(address=address_2)

        self.assertEqual(submitted_passport.stamps.count(), 1)
        self.assertEqual(submitted_passport.stamps.all()[0].provider, "Google")

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[
            copy.deepcopy(mock_passport_with_soon_to_be_expired_stamp),
            copy.deepcopy(mock_passport_google),
        ],
    )
    def test_update_dupe_stamps_with_newest_expiry(
        self, aget_passport, validate_credential
    ):
        """
        Test the updating of stamps with the newest expiry date if a stamp with the same hash is submitted
        """

        # Create an address
        address = self.account.address

        # Create a scorer
        scorer = Community.objects.create(
            name="The Scorer",
            description="A great scorer",
            account=self.user_account,
        )

        # Create a stamp that's already saved in the db with the same hash as the stamp being submitted, but older expiry date
        CeramicCache.objects.create(
            address=address,
            provider="Google",
            stamp=google_credential_soon_to_be_expired,
        )

        # Score the passport
        score_passport(scorer.id, address)

        # Get the soon-to-be expired stamp
        soon_to_be_expired_stamp = Stamp.objects.get(provider="Google")

        # Get the passport with the soon-to-be expired stamp
        passport_with_soon_to_be_expired = Passport.objects.get(address=address)

        # Check that the passport has 1 stamp
        self.assertEqual(passport_with_soon_to_be_expired.stamps.count(), 1)

        # Check that the passport has the soon-to-be expired stamp
        self.assertEqual(
            passport_with_soon_to_be_expired.stamps.all()[0].credential[
                "expirationDate"
            ],
            soon_to_be_expired_stamp.credential["expirationDate"],
        )

        # Now, submit the passport again but with a stamp with a newer expiry date
        CeramicCache.objects.update(
            address=address,
            provider="Google",
            stamp=google_credential,
        )

        # Score the passport again
        score_passport(scorer.id, address)

        # Get the updated stamp
        updated_stamp = Stamp.objects.get(provider="Google")

        # Get the Passport with updated stamp
        passport_with_updated_stamp = Passport.objects.get(address=address)

        # Passport should have the updated stamp with the newer expiry date
        self.assertEqual(
            passport_with_updated_stamp.stamps.all()[0].credential["expirationDate"],
            updated_stamp.credential["expirationDate"],
        )

        # passport should have only one stamp
        self.assertEqual(passport_with_updated_stamp.stamps.count(), 1)
