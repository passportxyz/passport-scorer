import json

import pytest
from ceramic_cache.models import CeramicCache
from django.test import Client
from datetime import datetime

pytestmark = pytest.mark.django_db

client = Client()


class TestBulkStampUpdates:
    def test_bulk_update(
        self, sample_providers, sample_addresses, sample_stamps, api_key
    ):
        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "address": sample_addresses[i],
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        params = {"stamps": bulk_payload}

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps",
            json.dumps(params),
            content_type="application/json",
            **{"HTTP_X-API-Key": api_key},
        )

        assert cache_stamp_response.status_code == 201
