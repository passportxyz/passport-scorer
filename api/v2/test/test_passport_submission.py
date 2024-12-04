import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase
from eth_account.messages import encode_defunct
from web3 import Web3

from account.models import Account, AccountAPIKey, Community, Nonce
from ceramic_cache.models import CeramicCache
from registry.models import Passport, Stamp
from registry.tasks import score_passport
from registry.utils import get_signing_message, verify_issuer
from scorer_weighted.models import BinaryWeightedScorer, Scorer, WeightedScorer

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

my_mnemonic = settings.TEST_MNEMONIC

now = datetime.now(timezone.utc)
ens_credential = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..b_ek317zi0Gq3SylrtJeODlbZuRrzfv-1TTBBNcBrDTMDBTikzPJMR2A1SuVcrfUl3MpNZ-zymaLGB5qz9xdDg",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:22.279Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": settings.TRUSTED_IAM_ISSUERS[0],
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expirationDate": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    "issuer": settings.TRUSTED_IAM_ISSUERS[0],
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expirationDate": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    "issuer": settings.TRUSTED_IAM_ISSUERS[0],
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expirationDate": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    "issuer": settings.TRUSTED_IAM_ISSUERS[0],
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expirationDate": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    "issuer": settings.TRUSTED_IAM_ISSUERS[0],
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expirationDate": (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    "issuer": settings.TRUSTED_IAM_ISSUERS[0],
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (now - timedelta(days=27)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expirationDate": (now + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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

mock_passport_expiration_date = min(
    datetime.fromisoformat(ens_credential["expirationDate"]),
    datetime.fromisoformat(google_credential["expirationDate"]),
)
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
    base_url = "/v2/stamps"

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
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION="Token 1234",
        )

        self.assertEqual(response.status_code, 401)

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

        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
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

        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
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

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    def test_submitted_passport_has_lower_case_address_value(
        self, aget_passport, validate_credential
    ):
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )

        self.assertEqual(response.status_code, 200)

        created_passport = Passport.objects.get(address=self.account.address.lower())
        self.assertEqual(created_passport.address, self.account.address.lower())

    # @patch("registry.atasks.validate_credential", side_effect=[[], []])
    # @patch(
    #     "registry.atasks.aget_passport",
    #     return_value=mock_passport,
    # )
    # def test_submit_passport_reused_nonce(self, aget_passport, validate_credential):
    #     """Test that submitting a reused nonce results in rejection"""

    #     for _ in [1, 2]:
    #         response = self.client.get(
    #             f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
    #             content_type="application/json",
    #             HTTP_AUTHORIZATION=f"Token {self.secret}",
    #         )

    #     self.assertEqual(response.json(), {"detail": "Invalid nonce."})
    #     self.assertEqual(response.status_code, 400)

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.atasks.aget_passport",
        return_value={},
    )
    def test_submitting_without_passport(self, aget_passport, validate_credential):
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)

        # Check if the passport data was saved to the database (data that we mock)
        # We do expect an empty passport to have been stored
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].stamps.count(), 0)

        assert response.status_code == 200
        assert response.json() == {
            "address": self.account.address.lower(),
            "score": "0.00000",
            "passing_score": False,
            "threshold": "20.00000",
            "last_score_timestamp": None,
            "expiration_timestamp": None,
            "error": "No Passport found for this address.",
            "stamps": {},
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

        expectedResponse = {
            "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
            "score": Decimal("0.93300"),
            "passing_score": False,
            "last_score_timestamp": "2023-01-11T16:35:23.938006+00:00",
            "expiration_timestamp": mock_passport_expiration_date.isoformat(),
            "threshold": "20.00000",
            "error": None,
            "stamps": {
                "Ens": {"dedup": False, "expiration_date": None, "score": "0.408"},
                "Google": {"dedup": False, "expiration_date": None, "score": "0.525"},
            },
        }

        expected2ndResponse = {
            "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
            "score": Decimal("0.93300"),
            "passing_score": False,
            "last_score_timestamp": "2023-01-11T16:35:23.938006+00:00",
            "expiration_timestamp": mock_passport_expiration_date.isoformat(),
            "threshold": "20.00000",
            "error": None,
            "stamps": {
                "Ens": {"dedup": False, "expiration_date": None, "score": "0.408"},
                "Google": {"dedup": False, "expiration_date": None, "score": "0.525"},
            },
        }

        # First submission
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
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

        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/tson",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
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

    @patch("registry.atasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.atasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    def test_submit_passport_with_binary_scorer_above_threshold(
        self, aget_passport, get_utc_time, validate_credential
    ):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""

        expected_score = "2.00000"

        scorer = BinaryWeightedScorer.objects.create(
            threshold=2,
            weights={"FirstEthTxnProvider": 1.0, "Google": 1, "Ens": 1.0},
            type=Scorer.Type.WEIGHTED_BINARY,
        )

        self.community.scorer = scorer
        self.community.save()

        expiration_date_list = [
            datetime.fromisoformat(s["credential"]["expirationDate"])
            for s in mock_passport["stamps"]
        ]

        # First submission
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(
            response_json,
            {
                "score": expected_score,
                "passing_score": True,
                "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
                "error": None,
                "expiration_timestamp": min(expiration_date_list).isoformat(),
                "last_score_timestamp": get_utc_time().isoformat(),
                "stamps": {
                    "Ens": {"dedup": False, "expiration_date": None, "score": "0.408"},
                    "Google": {
                        "dedup": False,
                        "expiration_date": None,
                        "score": "0.525",
                    },
                },
                "threshold": "2.00000",
            },
        )

    @patch("registry.atasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.atasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    def test_submit_passport_with_binary_scorer_below_threshold(
        self, aget_passport, get_utc_time, validate_credential
    ):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""

        expected_score = "2.00000"

        scorer = BinaryWeightedScorer.objects.create(
            threshold=20,
            weights={"FirstEthTxnProvider": 1.0, "Google": 1, "Ens": 1.0},
            type=Scorer.Type.WEIGHTED_BINARY,
        )

        self.community.scorer = scorer
        self.community.save()
        expiration_date_list = [
            datetime.fromisoformat(s["credential"]["expirationDate"])
            for s in mock_passport["stamps"]
        ]
        # First submission
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(
            response_json,
            {
                "score": expected_score,
                "passing_score": False,
                "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
                "error": None,
                "expiration_timestamp": min(expiration_date_list).isoformat(),
                "last_score_timestamp": get_utc_time().isoformat(),
                "stamp_scores": {"Ens": "1.0", "Google": "1.0"},
                "threshold": "20.00000",
            },
        )

    # TODO: add tests that verifies that returned threshold is from score when not resdcoring (theoretically threshold could change ...)

    @patch("registry.atasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.atasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    def test_submit_passport_with_non_binary_scorer_above_threshold(
        self, aget_passport, get_utc_time, validate_credential
    ):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""

        expected_score = "22.00000"

        scorer = WeightedScorer.objects.create(
            weights={"FirstEthTxnProvider": 11.0, "Google": 11, "Ens": 11.0},
            type=Scorer.Type.WEIGHTED,
        )
        self.community.scorer = scorer
        self.community.save()
        expiration_date_list = [
            datetime.fromisoformat(s["credential"]["expirationDate"])
            for s in mock_passport["stamps"]
        ]

        # First submission
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json["score"], expected_score)
        self.assertEqual(response_json["passing_score"], True)
        self.assertEqual(
            response_json,
            {
                "score": expected_score,
                "passing_score": True,
                "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
                "error": None,
                "expiration_timestamp": min(expiration_date_list).isoformat(),
                "last_score_timestamp": get_utc_time().isoformat(),
                "stamp_scores": {"Ens": "11.0", "Google": "11.0"},
                "threshold": "20.00000",
            },
        )

    @patch("registry.atasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.atasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    def test_submit_passport_with_non_binary_scorer_below_threshold(
        self, aget_passport, get_utc_time, validate_credential
    ):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""

        expected_score = "2.00000"

        scorer = WeightedScorer.objects.create(
            weights={"FirstEthTxnProvider": 1.0, "Google": 1.0, "Ens": 1.0},
            type=Scorer.Type.WEIGHTED,
        )
        self.community.scorer = scorer
        self.community.save()
        expiration_date_list = [
            datetime.fromisoformat(s["credential"]["expirationDate"])
            for s in mock_passport["stamps"]
        ]

        # First submission
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(
            response_json,
            {
                "score": expected_score,
                "passing_score": False,
                "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
                "error": None,
                "expiration_timestamp": min(expiration_date_list).isoformat(),
                "last_score_timestamp": get_utc_time().isoformat(),
                "stamp_scores": {"Ens": "1.0", "Google": "1.0"},
                "threshold": "20.00000",
            },
        )

    @patch("registry.atasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.atasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    def test_submit_passport_with_binary_scorer_below_threshold(
        self, aget_passport, get_utc_time, validate_credential
    ):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""

        expected_score = "2"

        scorer = BinaryWeightedScorer.objects.create(
            threshold=20,
            weights={"FirstEthTxnProvider": 1.0, "Google": 1, "Ens": 1.0},
            type=Scorer.Type.WEIGHTED_BINARY,
        )

        self.community.scorer = scorer
        self.community.save()
        expiration_date_list = [
            datetime.fromisoformat(s["credential"]["expirationDate"])
            for s in mock_passport["stamps"]
        ]
        # First submission
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(
            response_json,
            {
                "score": expected_score,
                "passing_score": False,
                "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
                "error": None,
                "expiration_timestamp": min(expiration_date_list).isoformat(),
                "last_score_timestamp": get_utc_time().isoformat(),
                "stamps": {
                    "Ens": {
                        "score": "1.0",
                        "dedup": False,
                        "expiration_date": None,
                    },
                    "Google": {
                        "score": "1.0",
                        "dedup": False,
                        "expiration_date": None,
                    },
                },
                "threshold": "20.00000",
            },
        )

    # TODO: add tests that verifies that returned threshold is from score when not resdcoring (theoretically threshold could change ...)

    @patch("registry.atasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.atasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    def test_submit_passport_with_non_binary_scorer_above_threshold(
        self, aget_passport, get_utc_time, validate_credential
    ):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""

        expected_score = "22"

        scorer = WeightedScorer.objects.create(
            weights={"FirstEthTxnProvider": 11.0, "Google": 11, "Ens": 11.0},
            type=Scorer.Type.WEIGHTED,
        )
        self.community.scorer = scorer
        self.community.save()
        expiration_date_list = [
            datetime.fromisoformat(s["credential"]["expirationDate"])
            for s in mock_passport["stamps"]
        ]

        # First submission
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json["score"], expected_score)
        self.assertEqual(response_json["passing_score"], True)
        self.assertEqual(
            response_json,
            {
                "score": expected_score,
                "passing_score": True,
                "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
                "error": None,
                "expiration_timestamp": min(expiration_date_list).isoformat(),
                "last_score_timestamp": get_utc_time().isoformat(),
                "stamps": {
                    "Ens": {"dedup": False, "expiration_date": None, "score": "0.408"},
                    "Google": {
                        "dedup": False,
                        "expiration_date": None,
                        "score": "0.525",
                    },
                },
                "threshold": "20",
            },
        )

    @patch("registry.atasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.atasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    @patch(
        "registry.atasks.aget_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    def test_submit_passport_with_non_binary_scorer_below_threshold(
        self, aget_passport, get_utc_time, validate_credential
    ):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""

        expected_score = "2"

        scorer = WeightedScorer.objects.create(
            weights={"FirstEthTxnProvider": 1.0, "Google": 1.0, "Ens": 1.0},
            type=Scorer.Type.WEIGHTED,
        )
        self.community.scorer = scorer
        self.community.save()
        expiration_date_list = [
            datetime.fromisoformat(s["credential"]["expirationDate"])
            for s in mock_passport["stamps"]
        ]

        # First submission
        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(
            response_json,
            {
                "score": expected_score,
                "passing_score": False,
                "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
                "error": None,
                "expiration_timestamp": min(expiration_date_list).isoformat(),
                "last_score_timestamp": get_utc_time().isoformat(),
                "stamps": {
                    "Ens": {"dedup": False, "expiration_date": None, "score": "0.408"},
                    "Google": {
                        "dedup": False,
                        "expiration_date": None,
                        "score": "0.525",
                    },
                },
                "threshold": "20",
            },
        )

    def test_submit_passport_accepts_scorer_id(self):
        """
        Make sure that the scorer_id is an acceptable parameter
        """

        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
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

        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
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

        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
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

        response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.account.address}",
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

        response = self.client.get(
            f"{self.base_url}/{self.community2.pk}/score/{self.account.address}",
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

        submission_response = self.client.get(
            f"{self.base_url}/{self.community.pk}/score/{self.mock_account.address}",
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
