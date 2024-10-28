from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client
from freezegun import freeze_time
from web3 import Web3

from ceramic_cache.models import CeramicCache
from registry.models import Event

pytestmark = pytest.mark.django_db


class TestPassportGetHistoricalScore:
    base_url = "/v2/stamps"

    def test_get_historical_score_invalid_api_key_permissions(
        self,
        scorer_account,
        scorer_api_key_no_permissions,
        scorer_community_with_binary_scorer,
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=2024-10-26",
            HTTP_AUTHORIZATION="Token " + scorer_api_key_no_permissions,
        )

        assert response.status_code == 403

    def test_get_historical_score_required_created_at(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()
        assert response.status_code == 422
        assert response_data["detail"] == [
            {"type": "missing", "loc": ["query", "created_at"], "msg": "Field required"}
        ]

    @freeze_time("2023-01-01")
    def test_get_historical_score_legacy_format(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        base_date = datetime(2023, 1, 1)
        # Create score event with legacy format
        Event.objects.create(
            action=Event.Action.SCORE_UPDATE,
            address=scorer_account.address,
            community=scorer_community_with_binary_scorer,
            data={
                "score": 1.0,
                "evidence": {
                    "type": "ThresholdScoreCheck",
                    "success": True,
                    "rawScore": "309.5190000000000054014570595",
                    "threshold": "100.00000",
                },
            },
        )

        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=2023-01-01",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert response_data["score"] == "309.5190000000000054014570595"
        assert response_data["threshold"] == "100.00000"
        assert response_data["passing_score"] is True
        assert response_data["last_score_timestamp"] == None
        assert response_data["expiration_timestamp"] == None

    @freeze_time("2023-01-01")
    def test_get_historical_score_new_format(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        base_date = datetime(2023, 1, 1)
        # Create score event with new format
        Event.objects.create(
            action=Event.Action.SCORE_UPDATE,
            address=scorer_account.address,
            community=scorer_community_with_binary_scorer,
            data={
                "pk": 15,
                "model": "registry.score",
                "fields": {
                    "error": None,
                    "score": "0",
                    "status": "DONE",
                    "evidence": {
                        "type": "ThresholdScoreCheck",
                        "success": False,
                        "rawScore": "5.459000000000000019095836024",
                        "threshold": "100.00000",
                    },
                    "passport": 15,
                    "stamp_scores": {"github": 10, "twitter": 15},
                    "expiration_date": "2024-11-21T22:09:10.687Z",
                    "last_score_timestamp": "2024-10-25T19:16:14.023Z",
                },
            },
        )

        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=2023-01-01",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert response_data["score"] == "5.459000000000000019095836024"
        assert response_data["threshold"] == "100.00000"
        assert response_data["passing_score"] is False
        assert response_data["last_score_timestamp"] == "2024-10-25T19:16:14.023Z"
        assert response_data["expiration_timestamp"] == "2024-11-21T22:09:10.687Z"
        assert response_data["stamp_scores"] == {"github": "10", "twitter": "15"}

    @freeze_time("2023-01-01")
    def test_get_historical_score_missing_fields(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        # Create score event with minimal data
        Event.objects.create(
            action=Event.Action.SCORE_UPDATE,
            address=scorer_account.address,
            community=scorer_community_with_binary_scorer,
            data={
                "evidence": {
                    "rawScore": "15",
                },
            },
        )

        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=2023-01-01",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert response_data["score"] == "15"
        assert response_data["threshold"] == "0"
        assert response_data["passing_score"] is True
        assert response_data["last_score_timestamp"] is None
        assert response_data["expiration_timestamp"] is None
        assert response_data["stamp_scores"] is None

    def test_get_historical_score_no_score_found(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=2023-01-01",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert response_data["address"] == scorer_account.address
        assert (
            response_data["status"]
            == f"No Score Found for {scorer_account.address} at 2023-01-01"
        )

    def test_get_historical_score_invalid_date(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=invalid-date",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 400
