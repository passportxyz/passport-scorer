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

    def test_bulk_update_create_doesnt_accept_greater_than_50_stamps(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []
        for i in range(0, 51):
            bulk_payload.append(
                {
                    "address": sample_address,
                    "provider": sample_providers[0],
                    "stamp": sample_stamps[0],
                }
            )

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 422
        assert cache_stamp_response.json() == {
            "detail": "You can not submit more than 50 stamps at a time."
        }

    def test_successful_bulk_delete(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []
        for i in range(0, 3):
            CeramicCache.objects.create(
                address=sample_address,
                provider=sample_providers[i],
                stamp=sample_stamps[i],
            )
            bulk_payload.append(
                {"address": sample_address, "provider": sample_providers[i]}
            )

        cache_stamp_response = client.delete(
            "/ceramic-cache/stamps",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert cache_stamp_response.json() == {
            "status": "success",
            "detail": "All stamps deleted",
        }

    def test_bulk_delete_indicates_a_subset_of_stamps_were_deleted(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []
        for i in range(0, 3):
            CeramicCache.objects.create(
                address=sample_address,
                provider=sample_providers[i],
                stamp=sample_stamps[i],
            )
            bulk_payload.append(
                {"address": sample_address, "provider": sample_providers[i]}
            )

        bulk_payload.append({"address": sample_address, "provider": "not-a-provider"})

        cache_stamp_response = client.delete(
            "/ceramic-cache/stamps",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert cache_stamp_response.json() == {
            "status": "partially deleted",
            "detail": "3 stamps deleted out of 4",
        }

    def test_bulk_delete_indicates_no_stamps_were_deleted(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []

        for i in range(0, 3):
            bulk_payload.append(
                {"address": sample_address, "provider": sample_providers[i]}
            )

        cache_stamp_response = client.delete(
            "/ceramic-cache/stamps",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 404
        assert cache_stamp_response.json() == {
            "detail": "Unable to find stamp to delete."
        }
