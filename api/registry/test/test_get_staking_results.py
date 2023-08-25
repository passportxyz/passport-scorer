from unittest.mock import patch

import pytest
from django.test import Client

mock_gql_response = {
    "users": [
        {
            "stakes": [{"stake": "10000000000000000000", "round": {"id": "2"}}],
            "xstakeAggregates": [],
        }
    ]
}

client = Client()


pytestmark = pytest.mark.django_db


class TestGetStakingResults:
    def test_successful_get_staking_results(self, client, scorer_api_key):
        with patch("registry.api.v1.gqlClient.execute") as mock_gql_execute:
            mock_gql_execute.return_value = mock_gql_response
            response = client.get(
                "/registry/gtc-stake/0x",
                HTTP_AUTHORIZATION="Token " + scorer_api_key,
            )  # Adjust the URL as needed
            assert response.status_code == 200
            assert response.json() == mock_gql_response

    def test_failed_graphql_request(self, client, scorer_api_key):
        with patch("registry.api.v1.gqlClient.execute") as mock_gql_execute:
            mock_gql_execute.side_effect = Exception(
                "GraphQL Request Failed"
            )  # Simulate an exception

            response = client.get(
                "/registry/gtc-stake/0x",
                HTTP_AUTHORIZATION="Token " + scorer_api_key,
            )

            assert response.status_code == 500

    def test_missing_address(self, client, scorer_api_key):
        response = client.get(
            "/registry/gtc-stake",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 404
