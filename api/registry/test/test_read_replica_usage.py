from unittest.mock import Mock, patch

import pytest
import registry.api.v1
from account.models import Community
from django.test import Client

pytestmark = pytest.mark.django_db


class TestPassportGetScore:
    def test_get_scores_is_using_read_replica_in_v1(
        self, scorer_api_key, scorer_community, settings
    ):
        settings.REGISTRY_API_READ_DB = "read_replica_0"

        with patch(
            "registry.api.v1.ScoreFilter",
            return_value=Mock(
                qs=[
                    {"passport": "1", "address": "0x1"},
                    {"passport": "2", "address": "0x2"},
                    {"passport": "3", "address": "0x3"},
                ],
            ),
        ):
            with patch.object(
                registry.api.v1.Community,
                "objects",
                using=Mock(return_value=Community.objects),
            ) as mock_community_objects:
                with patch.object(
                    registry.api.v1.Score, "objects", return_value=Mock()
                ) as mock_score_objects:
                    client = Client()
                    response = client.get(
                        f"/registry/score/{scorer_community.id}?limit={100}&offset={0}",
                        HTTP_AUTHORIZATION="Token " + scorer_api_key,
                    )
                    assert response.status_code == 200
                    assert mock_community_objects.using.call_count == 2
                    assert mock_community_objects.using.mock_calls[0].args == (
                        "read_replica_0",
                    )
                    assert mock_community_objects.using.mock_calls[1].args == (
                        "read_replica_0",
                    )
                    mock_score_objects.using.assert_called_once_with("read_replica_0")

    def test_get_scores_is_using_read_replica_in_v2(
        self, scorer_api_key, scorer_community, settings
    ):
        settings.REGISTRY_API_READ_DB = "read_replica_0"
        with patch(
            "registry.api.v1.ScoreFilter",
            return_value=Mock(
                qs=[
                    {"passport": "1", "address": "0x1"},
                    {"passport": "2", "address": "0x2"},
                    {"passport": "3", "address": "0x3"},
                ],
            ),
        ):
            with patch.object(
                registry.api.v1.Community,
                "objects",
                using=Mock(return_value=Community.objects),
            ) as mock_community_objects:
                with patch.object(
                    registry.api.v1.Score, "objects", return_value=Mock()
                ) as mock_score_objects:
                    client = Client()
                    response = client.get(
                        f"/registry/score/{scorer_community.id}?limit={100}&offset={0}",
                        HTTP_AUTHORIZATION="Token " + scorer_api_key,
                    )

                    assert response.status_code == 200
                    assert mock_community_objects.using.call_count == 2
                    assert mock_community_objects.using.mock_calls[0].args == (
                        "read_replica_0",
                    )
                    assert mock_community_objects.using.mock_calls[1].args == (
                        "read_replica_0",
                    )
                    mock_score_objects.using.assert_called_once_with("read_replica_0")
