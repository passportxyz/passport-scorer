import pytest
from django.test import Client
from ceramic_cache.models import CeramicCache
from datetime import datetime

pytestmark = pytest.mark.django_db

client = Client()


class TestGetStamp:
    def test_succesfully_get_stamp(
        self, sample_provider, sample_address, verifiable_credential
    ):
        CeramicCache.objects.create(
            address=sample_address,
            provider=sample_provider,
            stamp=verifiable_credential,
        )

        response = client.get(
            f"/ceramic-cache/stamp?address={sample_address}",
            **{"HTTP_X_API_KEY": "supersecret"},
        )

        first_stamp = response.json()["stamps"][0]

        assert response.status_code is 200
        assert first_stamp["address"] == sample_address.lower()
        assert first_stamp["provider"] == sample_provider
        assert first_stamp["stamp"] == verifiable_credential

    def test_get_stamp_returns_empty_list_if_no_stamps_exist(self, sample_address):
        response = client.get(
            f"/ceramic-cache/stamp?address={sample_address}",
            **{"HTTP_X_API_KEY": "supersecret"},
        )

        assert response.status_code is 200
        assert response.json()["stamps"] == []

    def test_deleted_stamps_are_not_returned(
        self, sample_address, sample_provider, verifiable_credential
    ):
        CeramicCache.objects.create(
            address=sample_address,
            provider=sample_provider,
            stamp=verifiable_credential,
        )
        CeramicCache.objects.create(
            address=sample_address,
            provider="Google",
            stamp=verifiable_credential,
            deleted_at=datetime.now(),
        )

        response = client.get(
            f"/ceramic-cache/stamp?address={sample_address}",
            **{"HTTP_X_API_KEY": "supersecret"},
        )

        assert response.status_code is 200
        assert len(response.json()["stamps"]) is 1
        assert response.json()["stamps"][0]["provider"] == sample_provider

    def test_get_stamp_returns_422_if_address_is_not_provided(self):
        response = client.get(
            "/ceramic-cache/stamp",
            **{"HTTP_X_API_KEY": "supersecret"},
        )

        assert response.status_code == 422
