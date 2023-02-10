import json

import pytest
from ceramic_cache.models import CeramicCache
from django.test import Client
from datetime import datetime

pytestmark = pytest.mark.django_db

client = Client()


class TestBulkStampUpdates:
    def test_bulk_create(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "address": sample_address,
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        assert len(cache_stamp_response.json()) == len(sample_providers)

    def test_bulk_update(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "address": sample_address,
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        assert len(cache_stamp_response.json()) == len(sample_providers)

        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "address": sample_address,
                    "provider": sample_providers[i],
                    "stamp": {"updated": True},
                }
            )

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        assert len(cache_stamp_response.json()) == len(sample_providers)
        for i in range(0, len(sample_providers)):
            assert cache_stamp_response.json()[i]["stamp"] == {"updated": True}
