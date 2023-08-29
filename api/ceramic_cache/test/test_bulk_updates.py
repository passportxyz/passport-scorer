import json
from datetime import datetime

import pytest
from ceramic_cache.api import get_address_from_did
from ceramic_cache.models import CeramicCache
from django.test import Client

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
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        assert len(cache_stamp_response.json()["stamps"]) == len(sample_providers)

    def test_bulk_update(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201

        assert len(cache_stamp_response.json()["stamps"]) == len(sample_providers)

        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "provider": sample_providers[i],
                    "stamp": {"updated": True},
                }
            )

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        assert len(cache_stamp_response.json()["stamps"]) == len(sample_providers)
        for i in range(0, len(sample_providers)):
            assert cache_stamp_response.json()["stamps"][i]["stamp"] == {
                "updated": True
            }

    def test_bulk_patch(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        # create two stamps
        bulk_payload = []
        for i in range(0, 2):
            bulk_payload.append(
                {
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        cache_stamp_response = client.patch(
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert len(cache_stamp_response.json()["stamps"]) == 2

        # Should have a stamp for the first provider, but not for the last provider
        assert CeramicCache.objects.filter(provider=sample_providers[0]).count() == 1
        assert (
            CeramicCache.objects.filter(
                provider=sample_providers[len(sample_providers) - 1]
            ).count()
            == 0
        )

        # patch all the stamps except the first, which is deleted
        bulk_payload = [{"provider": sample_providers[0]}]
        for i in range(1, len(sample_providers)):
            bulk_payload.append(
                {
                    "provider": sample_providers[i],
                    "stamp": {"updated": True},
                }
            )

        cache_stamp_response = client.patch(
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert len(cache_stamp_response.json()["stamps"]) == len(sample_providers) - 1

        # Should no longer have a stamp for the first provider, but now have one for the last provider
        assert CeramicCache.objects.filter(provider=sample_providers[0]).count() == 0
        assert (
            CeramicCache.objects.filter(
                provider=sample_providers[len(sample_providers) - 1]
            ).count()
            == 1
        )

    def test_bulk_update_create_doesnt_accept_greater_than_100_stamps(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []
        for i in range(0, 101):
            bulk_payload.append(
                {
                    "provider": sample_providers[0],
                    "stamp": sample_stamps[0],
                }
            )

        cache_stamp_response = client.post(
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 422
        assert cache_stamp_response.json() == {
            "detail": "You have submitted too many stamps."
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
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert cache_stamp_response.json()["success"] == True
        assert len(cache_stamp_response.json()["stamps"]) == 0

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
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert cache_stamp_response.json()["success"] == True

    def test_bulk_delete_indicates_no_stamps_were_deleted(
        self, sample_providers, sample_address, sample_stamps, sample_token
    ):
        bulk_payload = []

        for i in range(0, 3):
            bulk_payload.append(
                {"address": sample_address, "provider": sample_providers[i]}
            )

        cache_stamp_response = client.delete(
            "/ceramic-cache/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 404
        assert cache_stamp_response.json() == {
            "detail": "Unable to find stamp to delete."
        }

    def test_get_address_from_did(self, sample_address):
        did = f"did:pkh:eip155:1:{sample_address}"
        address = get_address_from_did(did)
        assert address == sample_address
