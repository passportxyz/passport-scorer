from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from django.test import Client

from ceramic_cache.api.schema import InternalV2ScoreResponse
from ceramic_cache.models import CeramicCache
from registry.models import Passport, Score

pytestmark = pytest.mark.django_db

client = Client()

future_expiration_date = datetime.now(timezone.utc) + timedelta(days=5)
past_expiration_date = datetime.now(timezone.utc) - timedelta(days=5)
last_score_timestamp = past_expiration_date


class TestBulkStampUpdates:
    base_url = "/ceramic-cache"
    stamp_version = CeramicCache.StampType.V1

    def test_get_score_when_no_stamps(
        self, scorer_passport, sample_token, mocker, ui_scorer
    ):
        mocker.patch("registry.atasks.get_utc_time", return_value=last_score_timestamp)

        score_get_response = client.get(
            f"{self.base_url}/score/{scorer_passport.address}",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert score_get_response.status_code == 200

        response_data = score_get_response.json()

        assert response_data == {
            "address": scorer_passport.address.lower(),
            "score": "0.00000",
            "last_score_timestamp": last_score_timestamp.isoformat(),
            "expiration_timestamp": None,
            "threshold": "20.00000",
            "passing_score": False,
            "error": None,
            "stamps": {},
            "points_data": None,
        }

    def test_get_score_when_score_not_expired(
        self, sample_address, sample_token, ui_scorer, mocker
    ):
        passport = Passport.objects.create(
            address=sample_address,
            community_id=ui_scorer,
        )

        # Create an score with expiration date in the future
        score = Score.objects.create(
            passport=passport,
            score=1,
            status=Score.Status.DONE,
            last_score_timestamp=past_expiration_date,
            expiration_date=future_expiration_date,
            error=None,
            stamp_scores={},
            evidence={
                "rawScore": "10",
                "type": "binary",
                "success": True,
                "threshold": "5",
            },
        )

        mocked_score_response_data = dict(
            address=passport.address.lower(),
            score="10.00000",
            passing_score=True,
            last_score_timestamp=score.last_score_timestamp.isoformat(),
            expiration_timestamp=score.expiration_date.isoformat(),
            threshold="5.00000",
            error=None,
            stamps={},
            points_data=None,
        )

        mocked_score_response = InternalV2ScoreResponse(**mocked_score_response_data)

        mocker.patch(
            "ceramic_cache.api.v1.get_detailed_score_response_for_address",
            side_effect=[mocked_score_response],
        )

        score_get_response = client.get(
            f"{self.base_url}/score/{passport.address}",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert score_get_response.status_code == 200

        response_data = score_get_response.json()

        assert response_data == {
            "address": "0xc79bfbf4e4824cdb65c71f2eeb2d7f2db5da1fb8",
            "score": "10.00000",
            "passing_score": True,
            "error": None,
            "expiration_timestamp": score.expiration_date.isoformat(),
            "last_score_timestamp": score.last_score_timestamp.isoformat(),
            "stamps": {},
            "threshold": "5.00000",
            "points_data": None,
        }

    def test_get_score_when_score_expired(
        self, sample_address, sample_token, ui_scorer, mocker
    ):
        passport = Passport.objects.create(
            address=sample_address,
            community_id=ui_scorer,
        )

        # Create an expired score.
        Score.objects.create(
            passport=passport,
            score=Decimal("1.000000000"),
            status=Score.Status.DONE,
            last_score_timestamp=past_expiration_date,
            expiration_date=past_expiration_date,  # This is an expired score
            error=None,
            stamp_scores={},
            evidence={
                "rawScore": 10.0,
                "type": "binary",
                "success": True,
                "threshold": 5.0,
            },
        )

        mocked_score_response_data = dict(
            address=passport.address.lower(),
            score="7.00000",
            passing_score=True,
            last_score_timestamp=future_expiration_date.isoformat(),
            expiration_timestamp=future_expiration_date.isoformat(),
            threshold="5.00000",
            error=None,
            stamps={},
            points_data=None,
        )

        mocked_score_response = InternalV2ScoreResponse(**mocked_score_response_data)

        mocker.patch(
            "ceramic_cache.api.v1.get_detailed_score_response_for_address",
            side_effect=[mocked_score_response],
        )

        score_get_response = client.get(
            f"{self.base_url}/score/{passport.address}",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert score_get_response.status_code == 200

        response_data = score_get_response.json()

        assert response_data == mocked_score_response_data
