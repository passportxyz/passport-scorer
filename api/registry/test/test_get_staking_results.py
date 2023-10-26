from unittest.mock import patch

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def gtc_staking_response():
    mock_response = [
        [
            {
                "id": 1,
                "event_type": "SelfStake",
                "round_id": 1,
                "staker": "0x",
                "address": None,
                "amount": "11000000000000000000",
                "staked": True,
                "block_number": 16,
                "tx_hash": "0x93",
            },
        ],
        [
            {
                "id": 2,
                "event_type": "Xstake",
                "round_id": 1,
                "staker": "0x09",
                "address": "0x",
                "amount": "10000000000000000000",
                "staked": True,
                "block_number": 16,
                "tx_hash": "0xd08",
            },
            {
                "id": 3,
                "event_type": "Xstake",
                "round_id": 1,
                "staker": "0x",
                "address": "0x6",
                "amount": "11000000000000000000",
                "staked": True,
                "block_number": 16,
                "tx_hash": "0x94",
            },
        ],
    ]

    return mock_response


class TestGetStakingResults:
    def test_successful_get_staking_results(self, scorer_api_key, gtc_staking_response):
        client = Client()
        response = client.get(
            "/registry/gtc-stake",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={"address": "0x", "round_id": 1},
        )

        print("response -=-=->", response)

        assert False
        # assert response.json() == mock_gql_response

    # def test_failed_graphql_request(self, client, scorer_api_key):
    #     with patch("registry.api.v1.gqlClient.execute") as mock_gql_execute:
    #         mock_gql_execute.side_effect = Exception(
    #             "GraphQL Request Failed"
    #         )  # Simulate an exception

    #         response = client.get(
    #             "/registry/gtc-stake/0x",
    #             HTTP_AUTHORIZATION="Token " + scorer_api_key,
    #         )

    #         assert response.status_code == 500

    # def test_missing_address(self, client, scorer_api_key):
    #     response = client.get(
    #         "/registry/gtc-stake",
    #         HTTP_AUTHORIZATION="Token " + scorer_api_key,
    #     )

    #     assert response.status_code == 404
