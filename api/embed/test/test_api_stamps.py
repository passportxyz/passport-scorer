import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import Client, TestCase

from account.models import Account, AccountAPIKey, Community
from ceramic_cache.models import CeramicCache
from registry.models import Score
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
mock_addresse = "0x0000000000000000000000000000000000000000"

mock_stamps = [
    {
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "id": mock_addresse,
            "hash": "v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
            "provider": "Ens",
        },
        "issuer": settings.TRUSTED_IAM_ISSUERS[0],
        "issuanceDate": (expiration_dates[0] - timedelta(days=30)).isoformat(),
        "expirationDate": expiration_dates[0].isoformat(),
        "proof": {
            "proofValue": "proof-v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
        },
    },
    {
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "id": mock_addresse,
            "hash": "0x88888",
            "provider": "Google",
        },
        "issuer": settings.TRUSTED_IAM_ISSUERS[0],
        "issuanceDate": (expiration_dates[1] - timedelta(days=30)).isoformat(),
        "expirationDate": expiration_dates[1].isoformat(),
        "proof": {
            "proofValue": "proof-0x88888",
        },
    },
    {
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "id": mock_addresse,
            "hash": "0x45678",
            "provider": "Gitcoin",
        },
        "issuer": settings.TRUSTED_IAM_ISSUERS[0],
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

        self.client = Client()

    def test_internal_api_key_is_required(self):
        """Test that the internal API key is required for the stamps request"""

        stamps_response = self.client.post(
            f"/internal/embed/stamps/{mock_addresse}",
            json.dumps({"scorer_id": self.community.id, "stamps": mock_stamps}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": "BAD_API_KEY"},
        )
        self.assertEqual(stamps_response.status_code, 401)

    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    def test_submit_valid_stamps(self, _test_submit_valid_stamps):
        """Test that the newly submitted stamps are correctly saved and scored"""

        stamps_response = self.client.post(
            f"/internal/embed/stamps/{mock_addresse}",
            json.dumps({"scorer_id": self.community.id, "stamps": mock_stamps}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )
        self.assertEqual(stamps_response.status_code, 200)
        data = stamps_response.json()

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
        }
        assert sorted(
            [d["stamp"] for d in data["stamps"]],
            key=lambda x: x["credentialSubject"]["provider"],
        ) == sorted(mock_stamps, key=lambda x: x["credentialSubject"]["provider"])

    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    def test_submit_additional_valid_stamps(self, _test_submit_valid_stamps):
        """Test that the newly submitted stamps are appended to already existing stamps"""

        # Create an initial stamp in the DB
        ceramic_cache = CeramicCache.from_verifiable_credential(mock_stamps[0])
        ceramic_cache.save()

        # Create the rest of the stamps via the POST request
        stamps_response = self.client.post(
            f"/internal/embed/stamps/{mock_addresse}",
            json.dumps({"scorer_id": self.community.id, "stamps": mock_stamps[1:]}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )
        self.assertEqual(stamps_response.status_code, 200)
        data = stamps_response.json()

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
        }
        assert sorted(
            [d["stamp"] for d in data["stamps"]],
            key=lambda x: x["credentialSubject"]["provider"],
        ) == sorted(mock_stamps, key=lambda x: x["credentialSubject"]["provider"])

    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    def test_storing_stamps_and_score(self, _test_submit_valid_stamps):
        """Existing stamps in the with the same providers are overriden and only counted once towards the score"""

        # Create the initial stamps in the DB
        ceramic_cache = CeramicCache.from_verifiable_credential(mock_stamps[0])
        ceramic_cache.save()
        ceramic_cache = CeramicCache.from_verifiable_credential(mock_stamps[1])
        ceramic_cache.save()
        ceramic_cache = CeramicCache.from_verifiable_credential(mock_stamps[2])
        ceramic_cache.save()

        # Create stamps with the same provider using the POST request
        stamps_response = self.client.post(
            f"/internal/embed/stamps/{mock_addresse}",
            json.dumps({"scorer_id": self.community.id, "stamps": mock_stamps}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )
        self.assertEqual(stamps_response.status_code, 200)
        data = stamps_response.json()

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
        }
        assert sorted(
            [d["stamp"] for d in data["stamps"]],
            key=lambda x: x["credentialSubject"]["provider"],
        ) == sorted(mock_stamps, key=lambda x: x["credentialSubject"]["provider"])

    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    def test_submitted_stamps_are_saved_properly(self, _test_submit_valid_stamps):
        """Test that the newly submitted stamps are stored in the DB properly"""

        # Create the rest of the stamps via the POST request
        stamps_response = self.client.post(
            f"/internal/embed/stamps/{mock_addresse}",
            json.dumps({"scorer_id": self.community.id, "stamps": mock_stamps}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )
        self.assertEqual(stamps_response.status_code, 200)

        # Check the stamps stored in the DB
        cc = list(CeramicCache.objects.all().values())
        assert len(cc) == len(mock_stamps)
        for idx, c in enumerate(cc):
            m = mock_stamps[idx]
            assert (
                c
                == {
                    # Just copy the automatically generated values over
                    "id": c["id"],
                    "created_at": c["created_at"],
                    "updated_at": c["updated_at"],
                    # Here are the values we control
                    "address": mock_addresse,
                    "provider": m["credentialSubject"]["provider"],
                    "compose_db_save_status": "pending",  # TODO: what state do we desire here ???
                    "compose_db_stream_id": "",
                    "deleted_at": None,
                    "expiration_date": datetime.fromisoformat(m["expirationDate"]),
                    "issuance_date": datetime.fromisoformat(m["issuanceDate"]),
                    "proof_value": m["proof"]["proofValue"],
                    "source_app": CeramicCache.SourceApp.EMBED.value,
                    "source_scorer_id": self.community.id,
                    "stamp": m,
                    "type": 1,
                }
            )

        # Check the score stored in the DB
        scores = Score.objects.filter(
            passport__address=mock_addresse, passport__community=self.community
        ).values()
        assert len(scores) == 1
        score = scores[0]
        assert score == {
            # Just copy the automatically generated values over
            "id": score["id"],
            "last_score_timestamp": score["last_score_timestamp"],
            "passport_id": score["passport_id"],
            # Here are the values we control
            "error": None,
            "evidence": {
                "rawScore": "45",
                "success": True,
                "threshold": "20.00000",
                "type": "ThresholdScoreCheck",
            },
            "expiration_date": min(expiration_dates),
            "score": Decimal("1.000000000"),
            "stamp_scores": {
                "Ens": 15.0,
                "Gitcoin": 15.0,
                "Google": 15.0,
            },
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
            "status": "DONE",
        }
