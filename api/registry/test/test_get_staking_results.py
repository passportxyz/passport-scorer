import pytest
from django.test import Client
from registry.models import GTCStakeEvent

pytestmark = pytest.mark.django_db

user_address = "0x00Ac00000e4AbE2d293586A1f4F9C73e5512121e"


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
        stakes = list(GTCStakeEvent.objects.all())

        client = Client()
        response = client.get(
            f"/registry/gtc-stake/{user_address}/1",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()["results"]
        assert response.status_code == 200

        # an extra stake event was added that is below the filtered amount, hence the minus 1
        assert len(stakes) - 1 == len(response_data)

    def test_item_in_filter_condition_is_not_present(
        self, scorer_api_key, gtc_staking_response
    ):
        client = Client()
        response = client.get(
            f"/registry/gtc-stake/{user_address}/1",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()["results"]
        assert response.status_code == 200

        for item in response_data:
            # ID 16 belongs to the item that does not meet the filter criteria
            assert item["id"] != 16

    def test_missing_address_error_response(self, scorer_api_key, gtc_staking_response):
        client = Client()
        response = client.get(
            f"/registry/gtc-stake//1",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 404

    def test_missing_round_id_error_response(
        self, scorer_api_key, gtc_staking_response
    ):
        client = Client()
        response = client.get(
            f"/registry/gtc-stake/{user_address}/",
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
