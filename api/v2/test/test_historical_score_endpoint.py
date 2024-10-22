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

    def test_get_historical_score_response_with_no_scores(
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

        assert response.status_code == 200
        assert len(response_data["items"]) == 0

    def test_successfully_get_paginated_historical_scores(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        i = 0
        while True:
            Event.objects.create(
                action=Event.Action.SCORE_UPDATE,
                address=scorer_account.address,
                community=scorer_community_with_binary_scorer,
                data={
                    "score": 1,
                    "evidence": {
                        "rawScore": 20 + i,
                        "type": "binary",
                        "success": True,
                        "threshold": 5,
                    },
                },
            )
            i += 1
            if i > 10:
                break

        client = Client()
        # First page request
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?limit=5",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        # Verify pagination links exist
        assert "next" in response_data
        assert "prev" in response_data
        # Verify number of items
        assert len(response_data["items"]) == 5

        # Verify item structure and ordering
        for idx, item in enumerate(response_data["items"]):
            assert item["address"].lower() == scorer_account.address.lower()
            assert item["score"] == "1"
            assert item["status"] == "DONE"
            assert "last_score_timestamp" in item
            assert item["evidence"]["type"] == "binary"
            assert item["evidence"]["success"] is True
            assert item["evidence"]["threshold"] == "5"
            # Verify descending order of rawScores (30, 29, 28, 27, 26)
            assert item["evidence"]["rawScore"] == str(30 - idx)

        # Get the next page using the next link
        next_url = response_data["next"].split("testserver")[1]
        response = client.get(
            next_url,
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()

        assert response.status_code == 200

        assert len(response_data["items"]) == 5
        # Verify the second page items (25, 24, 23, 22, 21)
        for idx, item in enumerate(response_data["items"]):
            assert item["evidence"]["rawScore"] == str(25 - idx)

    def test_successfully_get_historical_scores(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        i = 1
        while True:
            Event.objects.create(
                action=Event.Action.SCORE_UPDATE,
                address=scorer_account.address,
                community=scorer_community_with_binary_scorer,
                data={
                    "score": 1,
                    "evidence": {
                        "rawScore": 20 + i,
                        "type": "binary",
                        "success": True,
                        "threshold": 5,
                    },
                },
            )
            i += 1
            if i > 10:
                break

        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == 10

    def test_get_historical_score_limit_exceeding_1000(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?limit=1001",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 400
        assert "Invalid limit" in response.json()["detail"]

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

    def test_get_historical_score_address_no_created_at(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        # Create a score event
        Event.objects.create(
            action=Event.Action.SCORE_UPDATE,
            address=scorer_account.address,
            community=scorer_community_with_binary_scorer,
            data={
                "score": 1,
                "evidence": {
                    "rawScore": 20,
                    "type": "binary",
                    "success": True,
                    "threshold": 5,
                },
            },
        )

        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == 1
        assert (
            response_data["items"][0]["address"].lower()
            == scorer_account.address.lower()
        )

    @freeze_time("2023-01-01")
    def test_get_historical_score_address_and_created_at(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        # Create multiple score events
        for i in range(3):
            Event.objects.create(
                action=Event.Action.SCORE_UPDATE,
                address=scorer_account.address,
                community=scorer_community_with_binary_scorer,
                data={
                    "score": i,
                    "evidence": {
                        "rawScore": 20 + i,
                        "type": "binary",
                        "success": True,
                        "threshold": 5,
                    },
                },
                created_at=datetime.now() - timedelta(days=i),
            )

        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=2023-01-01T00:00:00",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == 1
        assert response_data["items"][0]["score"] == "2"

    @freeze_time("2023-01-01")
    def test_get_historical_score_created_at_no_address(
        self,
        scorer_account,
        scorer_api_key,
        scorer_community_with_binary_scorer,
    ):
        # Create multiple score events for different addresses
        addresses = [Web3.to_checksum_address(f"0x{i:040x}") for i in range(5)]
        for i, address in enumerate(addresses):
            Event.objects.create(
                action=Event.Action.SCORE_UPDATE,
                address=address,
                community=scorer_community_with_binary_scorer,
                data={
                    "score": i,
                    "evidence": {
                        "rawScore": 20 + i,
                        "type": "binary",
                        "success": True,
                        "threshold": 5,
                    },
                },
                created_at=datetime.now() - timedelta(days=i),
            )

        client = Client()
        response = client.get(
            f"{self.base_url}/{scorer_community_with_binary_scorer.id}/score/{scorer_account.address}/history?created_at=2023-01-01T00:00:00",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == 0
