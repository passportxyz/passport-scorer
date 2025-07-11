import json
from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import Client, TestCase

from account.models import Account, AccountAPIKey, Community
from ceramic_cache.models import CeramicCache
from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from scorer_weighted.models import BinaryWeightedScorer, Scorer

# Avoids type issues in standard django models
user_manager = cast(UserManager, get_user_model().objects)


now = datetime.now(timezone.utc)
expiration_dates = [
    now + timedelta(days=2),
    now + timedelta(days=1),
    now + timedelta(days=3),
]

providers = ["Ens", "Google", "Gitcoin"]
mock_address = "0x0000000000000000000000000000000000000000"

trusted_issuer = [
    issuer for issuer in settings.TRUSTED_IAM_ISSUERS if issuer.startswith("did:ethr:")
][0]

mock_stamps = [
    {
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "id": mock_address,
            "hash": "v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
            "provider": "Ens",
        },
        "issuer": trusted_issuer,
        "issuanceDate": (expiration_dates[0] - timedelta(days=30)).isoformat(),
        "expirationDate": expiration_dates[0].isoformat(),
        "proof": {
            "proofValue": "proof-v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
        },
    },
    {
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "id": mock_address,
            "hash": "0x88888",
            "provider": "Google",
        },
        "issuer": trusted_issuer,
        "issuanceDate": (expiration_dates[1] - timedelta(days=30)).isoformat(),
        "expirationDate": expiration_dates[1].isoformat(),
        "proof": {
            "proofValue": "proof-0x88888",
        },
    },
    {
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "id": mock_address,
            "hash": "0x45678",
            "provider": "Gitcoin",
        },
        "issuer": trusted_issuer,
        "issuanceDate": (expiration_dates[2] - timedelta(days=30)).isoformat(),
        "expirationDate": expiration_dates[2].isoformat(),
        "proof": {
            "proofValue": "proof-0x45678",
        },
    },
]
mock_stamps = sorted(mock_stamps, key=lambda x: x["credentialSubject"]["provider"])


class StampsApiTestCase(TestCase):
    def setUp(self):
        user_manager.create_user(username="admin", password="12345")

        self.user = user_manager.create_user(username="testuser-1", password="12345")

        (self.account, _) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )

        config = WeightConfiguration.objects.create(
            version="v1",
            threshold=5.0,
            active=True,
            description="Test",
        )

        for provider, weight in GITCOIN_PASSPORT_WEIGHTS.items():
            WeightConfigurationItem.objects.create(
                weight_configuration=config,
                provider=provider,
                weight=float(weight),
            )

        self.community = Community.objects.create(
            account=self.account,
            name="Community for user 2",
            description="test",
            scorer=BinaryWeightedScorer.objects.create(
                type=Scorer.Type.WEIGHTED_BINARY,
                threshold=20.0,
                weights={provider: 15 for provider in providers},
            ),
        )

        (_, api_key) = AccountAPIKey.objects.create_key(
            account=self.account,
            name="Token for user 1",
        )
        self.api_key = api_key

        for s in mock_stamps:
            CeramicCache.objects.create(
                address=mock_address,
                provider=s["credentialSubject"]["provider"],
                proof_value=s["proof"]["proofValue"],
                stamp=s,
            )

        self.client = Client()

    def test_internal_api_key_is_required(self):
        """Test that the internal API key is required for the stamps request"""

        stamps_response = self.client.post(
            f"/internal/embed/stamps/{mock_address}",
            json.dumps({"scorer_id": self.community.id, "stamps": mock_stamps}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": "BAD_API_KEY"},
        )
        self.assertEqual(stamps_response.status_code, 401)

    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    def test_compute_score_succefully(self, _test_submit_valid_stamps):
        """Test that the score is correctly computed and returned"""

        stamps_response = self.client.get(
            f"/internal/embed/score/{self.community.id}/{mock_address}",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )
        data = stamps_response.json()
        self.assertEqual(stamps_response.status_code, 200)

        assert data["success"] == True

        last_score_timestamp = data["score"].pop("last_score_timestamp")

        assert datetime.fromisoformat(last_score_timestamp) - datetime.now(
            timezone.utc
        ) < timedelta(seconds=2)
        assert data["score"] == {
            "address": "0x0000000000000000000000000000000000000000",
            "error": None,
            "expiration_timestamp": min(expiration_dates).isoformat(),
            "passing_score": True,
            "score": "45.00000",
            "stamps": {
                "Ens": {
                    "dedup": False,
                    "expiration_date": expiration_dates[0].isoformat(),
                    "score": "15.00000",
                },
                "Google": {
                    "dedup": False,
                    "expiration_date": expiration_dates[1].isoformat(),
                    "score": "15.00000",
                },
                "Gitcoin": {
                    "dedup": False,
                    "expiration_date": expiration_dates[2].isoformat(),
                    "score": "15.00000",
                },
            },
            "threshold": "20.00000",
            "points_data": None,
            "possible_points_data": None,
        }
        assert sorted(
            [d["stamp"] for d in data["stamps"]],
            key=lambda x: x["credentialSubject"]["provider"],
        ) == sorted(mock_stamps, key=lambda x: x["credentialSubject"]["provider"])

    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    def test_submit_additional_valid_stamps(self, _test_submit_valid_stamps):
        """Test error handling when bad scorer_id is provided"""

        stamps_response = self.client.get(
            f"/internal/embed/score/1234/{mock_address}",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )
        self.assertEqual(stamps_response.status_code, 400)
        data = stamps_response.json()

        assert data == {"detail": "Invalid scorer_id"}
