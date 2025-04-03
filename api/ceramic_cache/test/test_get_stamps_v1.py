from datetime import datetime

import pytest
from django.test import Client

from ceramic_cache.models import CeramicCache

pytestmark = pytest.mark.django_db

client = Client()


class TestGetStamp:
    base_url = "/ceramic-cache"
    stamp_version = CeramicCache.StampType.V1

    def test_succesfully_get_stamp(
        self, sample_provider, sample_address, verifiable_credential, ui_scorer
    ):
        CeramicCache.objects.create(
            type=self.stamp_version,
            address=sample_address,
            provider=sample_provider,
            stamp=verifiable_credential,
        )

        response = client.get(
            f"{self.base_url}/stamp?address={sample_address}",
        )

        first_stamp = response.json()["stamps"][0]

        assert response.status_code is 200
        assert first_stamp["address"] == sample_address.lower()
        assert first_stamp["provider"] == sample_provider
        assert first_stamp["stamp"] == verifiable_credential

    def test_get_stamp_returns_empty_list_if_no_stamps_exist(
        self, sample_address, ui_scorer
    ):
        response = client.get(
            f"{self.base_url}/stamp?address={sample_address}",
        )

        assert response.status_code is 200
        assert response.json()["stamps"] == []

    def test_get_stamp_returns_422_if_address_is_not_provided(self):
        response = client.get(
            f"{self.base_url}/stamp",
        )

        assert response.status_code == 422
