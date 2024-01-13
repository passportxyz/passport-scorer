import pytest
from django.test import Client
from registry.models import GTCStakeEvent

pytestmark = pytest.mark.django_db

user_address = "0x00Ac00000e4AbE2d293586A1f4F9C73e5512121e"


class TestGetStakingResults:
    @pytest.fixture
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

    @pytest.fixture
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

    @pytest.fixture
    def test_missing_address_error_response(self, scorer_api_key, gtc_staking_response):
        client = Client()
        response = client.get(
            "/registry/gtc-stake//1",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 404

    @pytest.fixture
    def test_missing_round_id_error_response(
        self, scorer_api_key, gtc_staking_response
    ):
        client = Client()
        response = client.get(
            f"/registry/gtc-stake/{user_address}/",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 404
