from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.test import Client
from stake.models import Stake

pytestmark = pytest.mark.django_db

other_user_address = "0x976EA74026E726554dB657fA54763abd0C3a0aa9"
twelve_weeks = 7257600


@pytest.fixture
def mock_stakes(sample_address):
    Stake.objects.create(
        chain="11155420",
        staker=sample_address,
        stakee=sample_address,
        current_amount=Decimal("100000000000000000000"),
        last_updated_in_block=Decimal("10000000"),
        unlock_time=datetime.now() + timedelta(days=90),
        lock_time=datetime.now() - timedelta(days=90),
    )
    Stake.objects.create(
        chain="11155420",
        staker=sample_address,
        stakee=other_user_address,
        current_amount=Decimal("200000000000000000000"),
        last_updated_in_block=Decimal("10000001"),
        unlock_time=datetime.now() + timedelta(days=91),
        lock_time=datetime.now() - timedelta(days=90),
    )
    Stake.objects.create(
        chain="11155420",
        staker=other_user_address,
        stakee=sample_address,
        current_amount=Decimal("350000000000000000000"),
        last_updated_in_block=Decimal("10000002"),
        unlock_time=datetime.now() + timedelta(days=92),
        lock_time=datetime.now() - timedelta(days=90),
    )
    Stake.objects.create(
        chain="1",
        staker=other_user_address,
        stakee=sample_address,
        current_amount=Decimal("475000000000000000000"),
        last_updated_in_block=Decimal("10000002"),
        unlock_time=datetime.now() + timedelta(days=92),
        lock_time=datetime.now() - timedelta(days=90),
    )


class TestGetStakingResults:
    def test_successful_get_staking_results(self, mock_stakes, sample_address):
        client = Client()
        response = client.get(
            f"/stake/gtc/{sample_address.lower()}",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )
        response_data = response.json()['items']
        print(response_data)
        assert response.status_code == 200

        # an extra stake event was added that is below the filtered amount, hence the minus 1
        assert len(response_data) == 4
        assert response_data[0]["staker"] == sample_address.lower()
        assert response_data[0]["chain"] == 11155420
        assert response_data[3]["staker"] == other_user_address.lower()
        assert response_data[3]["chain"] == 1

    def test_failed_auth(self, mock_stakes, sample_address):
        client = Client()
        response = client.get(f"/stake/gtc/{sample_address}", HTTP_AUTHORIZATION="None")

        assert response.status_code == 401

    def test_ceramic_cache_endpoint_success(
        self, sample_token, mock_stakes, sample_address
    ):
        client = Client()
        response = client.get(
            "/ceramic-cache/stake/gtc",
            HTTP_AUTHORIZATION="Bearer " + sample_token,
        )

        response_data = response.json()['items']
        assert response.status_code == 200

        # an extra stake event was added that is below the filtered amount, hence the minus 1
        assert len(response_data) == 4
        assert response_data[0]["staker"] == sample_address.lower()
        assert response_data[0]["chain"] == 11155420
        assert response_data[3]["staker"] == other_user_address.lower()
        assert response_data[3]["chain"] == 1

    def test_ceramic_cache_endpoint_failed_auth(self, mock_stakes):
        client = Client()
        response = client.get(
            "/ceramic-cache/stake/gtc",
            HTTP_AUTHORIZATION="Bearer 69420",
        )

        assert response.status_code == 401
