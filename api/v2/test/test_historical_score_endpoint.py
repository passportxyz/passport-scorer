from datetime import datetime, timedelta
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
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history",
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
        assert response.status_code == 400
        assert (
            response_data["detail"] == "You must provide created_at as a query param."
        )

    # @freeze_time("2023-01-01")
    # def test_get_historical_score_address_at_timestamp(
    #     self,
    #     scorer_account,
    #     scorer_api_key,
    #     scorer_community_with_binary_scorer,
    # ):
    #     base_date = datetime(2023, 1, 1)
    #     # Create multiple score events
    #     for i in range(3):
    #         with freeze_time(base_date + timedelta(days=i)):
    #             Event.objects.create(
    #                 action=Event.Action.SCORE_UPDATE,
    #                 address=scorer_account.address,
    #                 community=scorer_community_with_binary_scorer,
    #                 data={
    #                     "score": i,
    #                     "evidence": {
    #                         "rawScore": 20 + i,
    #                         "type": "binary",
    #                         "success": True,
    #                         "threshold": 5,
    #                     },
    #                 },
    #             )

    #     client = Client()
    #     response = client.get(
    #         f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=2023-01-01T00:00:00",
    #         HTTP_AUTHORIZATION="Token " + scorer_api_key,
    #     )
    #     response_data = response.json()

    #     assert response.status_code == 200
    #     assert response_data["score"] == "0"
