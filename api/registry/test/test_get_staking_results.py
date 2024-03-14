from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.test import Client
from registry.models import GTCStakeEvent, Stake

pytestmark = pytest.mark.django_db

user_address = "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"
other_user_address = "0x976EA74026E726554dB657fA54763abd0C3a0aa9"


class TestGetLegacyStakingResults:
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
            "/registry/gtc-stake//1",
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
        )

        assert response.status_code == 404


twelve_weeks = 7257600


@pytest.fixture
def mock_stakes():
    Stake.objects.create(
        chain=Stake.Chain.ETHEREUM,
        staker=user_address,
        stakee=user_address,
        current_amount=Decimal("100000000000000000000"),
        last_updated_in_block=Decimal("10000000"),
        unlock_time=datetime.now() + timedelta(days=90),
        lock_duration=twelve_weeks,
    )
    Stake.objects.create(
        chain=Stake.Chain.ETHEREUM,
        staker=user_address,
        stakee=other_user_address,
        current_amount=Decimal("200000000000000000000"),
        last_updated_in_block=Decimal("10000001"),
        unlock_time=datetime.now() + timedelta(days=91),
        lock_duration=twelve_weeks,
    )
    Stake.objects.create(
        chain=Stake.Chain.ETHEREUM,
        staker=other_user_address,
        stakee=user_address,
        current_amount=Decimal("350000000000000000000"),
        last_updated_in_block=Decimal("10000002"),
        unlock_time=datetime.now() + timedelta(days=92),
        lock_duration=twelve_weeks,
    )
    Stake.objects.create(
        chain=Stake.Chain.OPTIMISM,
        staker=other_user_address,
        stakee=user_address,
        current_amount=Decimal("475000000000000000000"),
        last_updated_in_block=Decimal("10000002"),
        unlock_time=datetime.now() + timedelta(days=92),
        lock_duration=twelve_weeks,
    )


class TestGetStakingResults:
    def test_successful_get_staking_results(self, scorer_api_key, mock_stakes):
        stakes = list(GTCStakeEvent.objects.all())

        client = Client()
        response = client.get(
            f"/registry/gtc-stake/{user_address}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()
        print(response_data)
        assert response.status_code == 200

        # an extra stake event was added that is below the filtered amount, hence the minus 1
        assert len(response_data) == 4
        assert response_data[0]["staker"] == user_address.lower()
        assert response_data[0]["chain"] == "ETHEREUM"
        assert response_data[3]["staker"] == other_user_address.lower()
        assert response_data[3]["chain"] == "OPTIMISM"
