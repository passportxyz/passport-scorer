import json
from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import TestCase
from test_api_stamps import (
    expiration_dates,
    mock_address,
    mock_stamps,
    providers,
    user_manager,
)

from account.models import Account, AccountAPIKey, Community
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext
from ceramic_cache.models import CeramicCache
from embed.lambda_fn import lambda_handler_get_score
from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from scorer_weighted.models import BinaryWeightedScorer, Scorer

# Avoids type issues in standard django models
user_manager = cast(UserManager, get_user_model().objects)


class GetScoreTestCase(TestCase):
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

    @patch("embed.lambda_fn.close_old_connections", side_effect=[None])
    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    def test_compute_score_succefully(
        self, _validate_credential, _close_old_connections
    ):
        """Test that the score is correctly computed and returned"""

        (api_key_obj, api_key) = AccountAPIKey.objects.create_key(
            account=self.account,
            name="Token for user 1",
        )

        event = {
            "headers": {"x-api-key": api_key},
            "path": f"/internal/embed/score/{self.community.id}/{mock_address}",
            "isBase64Encoded": False,
        }

        result = lambda_handler_get_score(event, MockContext())

        data = json.loads(result["body"])

        assert result["headers"] == {
            "Content-Type": "application/json",
        }
        assert result["statusCode"] == 200

        last_score_timestamp = data["score"].pop("last_score_timestamp")

        assert data["success"] == True
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
        assert _close_old_connections.call_count == 1

    @patch("embed.lambda_fn.close_old_connections", side_effect=[None])
    @patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    def test_invalid_scorer_id(self, _validate_credential, _close_old_connections):
        """Test error handling when bad scorer_id is provided"""

        (api_key_obj, api_key) = AccountAPIKey.objects.create_key(
            account=self.account,
            name="Token for user 1",
        )

        event = {
            "headers": {"x-api-key": api_key},
            "path": f"/internal/embed/score/1234/{mock_address}",
            "isBase64Encoded": False,
        }

        result = lambda_handler_get_score(event, MockContext())

        data = json.loads(result["body"])

        assert result["headers"] == {
            "Content-Type": "application/json",
            "Access-Control-Allow-Headers": "Accept,Accept-Encoding,Authorization,Content-Type,Dnt,Origin,User-Agent,X-Csrftoken,X-Requested-With,X-Api-Key",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Origin": "*",
        }
        assert result["statusCode"] == 400

        assert data == {"detail": "Invalid scorer_id"}

        assert _close_old_connections.call_count == 1
