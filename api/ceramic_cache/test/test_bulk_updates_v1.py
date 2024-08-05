import json
from datetime import datetime

import pytest
from django.test import Client

from ceramic_cache.api.v1 import get_address_from_did
from ceramic_cache.models import CeramicCache

pytestmark = pytest.mark.django_db

client = Client()


class TestBulkStampUpdates:
    base_url = "/ceramic-cache"
    stamp_version = CeramicCache.StampType.V1

    def test_bulk_create(
        self,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        ui_scorer,
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
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        stamps = cache_stamp_response.json()["stamps"]
        assert len(stamps) == len(sample_providers)
        assert stamps[0]["id"] is not None

    def test_bulk_update(
        self,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        scorer_account,
        ui_scorer,
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
            f"{self.base_url}/stamps/bulk",
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
                    "stamp": {"updated": True, "proof": {"proofValue": "updated"}},
                }
            )

        cache_stamp_response = client.post(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201

        stamps = cache_stamp_response.json()["stamps"]

        assert len(stamps) == len(sample_providers)
        for i in range(0, len(sample_providers)):
            assert stamps[i]["stamp"]["updated"] == True
            assert stamps[i]["id"] is not None

    def test_bulk_patch(
        self,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        ui_scorer,
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
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        stamps = cache_stamp_response.json()["stamps"]
        assert len(stamps) == 2
        assert stamps[0]["id"] is not None

        # Should have a stamp for the first provider, but not for last provider
        assert (
            CeramicCache.objects.filter(
                type=self.stamp_version, provider=sample_providers[0]
            ).count()
            == 1
        )

        assert (
            CeramicCache.objects.filter(
                type=self.stamp_version,
                provider=sample_providers[len(sample_providers) - 1],
            ).count()
            == 0
        )

        # patch all the stamps except the first, which is deleted
        bulk_payload = [{"provider": sample_providers[0]}]
        for i in range(1, len(sample_providers)):
            bulk_payload.append(
                {
                    "provider": sample_providers[i],
                    "stamp": {"updated": True, "proof": {"proofValue": "test"}},
                }
            )

        cache_stamp_response = client.patch(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert len(cache_stamp_response.json()["stamps"]) == len(sample_providers) - 1

        # Should now have a stamp for the last provider, but stamp for first provider should be marked as deleted
        assert (
            CeramicCache.objects.filter(
                type=self.stamp_version,
                provider=sample_providers[0],
                deleted_at__isnull=True,
            ).count()
            == 0
        )

        assert (
            CeramicCache.objects.filter(
                type=self.stamp_version,
                provider=sample_providers[0],
                deleted_at__isnull=False,
            ).count()
            == 1
        )

        assert (
            CeramicCache.objects.filter(
                type=self.stamp_version,
                provider=sample_providers[len(sample_providers) - 1],
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
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 422
        assert cache_stamp_response.json() == {
            "detail": "You have submitted too many stamps."
        }

    def test_successful_bulk_delete(
        self, sample_providers, sample_address, sample_stamps, sample_token, ui_scorer
    ):
        bulk_payload = []
        for i in range(0, 3):
            CeramicCache.objects.create(
                type=self.stamp_version,
                address=sample_address,
                provider=sample_providers[i],
                stamp=sample_stamps[i],
            )
            bulk_payload.append(
                {"address": sample_address, "provider": sample_providers[i]}
            )

        cache_stamp_response = client.delete(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert cache_stamp_response.json()["success"] == True
        assert len(cache_stamp_response.json()["stamps"]) == 0

    def test_bulk_delete_indicates_a_subset_of_stamps_were_deleted(
        self,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        ui_scorer,
    ):
        bulk_payload = []
        for i in range(0, 3):
            CeramicCache.objects.create(
                type=self.stamp_version,
                address=sample_address,
                provider=sample_providers[i],
                stamp=sample_stamps[i],
            )
            bulk_payload.append(
                {"address": sample_address, "provider": sample_providers[i]}
            )

        bulk_payload.append({"address": sample_address, "provider": "not-a-provider"})

        cache_stamp_response = client.delete(
            f"{self.base_url}/stamps/bulk",
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
            f"{self.base_url}/stamps/bulk",
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


class TestComposeDBBulkStampUpdates:
    base_url = "/ceramic-cache"
    stamp_version = CeramicCache.StampType.V1

    def test_success_bulk_update_compose_db_status(
        self,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        ui_scorer,
    ):
        # Create stamps first
        create_response = client.post(
            f"{self.base_url}/stamps/bulk",
            json.dumps(
                [
                    {
                        "provider": sample_providers[0],
                        "stamp": sample_stamps[0],
                    },
                    {
                        "provider": sample_providers[1],
                        "stamp": sample_stamps[1],
                    },
                    # This one will stay pending
                    {
                        "provider": sample_providers[2],
                        "stamp": sample_stamps[2],
                    },
                ]
            ),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )
        assert create_response.status_code == 201

        ids = [stamp["id"] for stamp in create_response.json()["stamps"]]

        missing_id = 1234564564564564564

        # Construct payload
        bulk_payload = [
            {
                "id": ids[0],
                "compose_db_save_status": "saved",
                "compose_db_stream_id": "stream-id-1",
            },
            {
                "id": ids[1],
                "compose_db_save_status": "failed",
            },
            # This is not valid, but should not interfere
            {
                "id": missing_id,
                "compose_db_save_status": "saved",
            },
        ]

        # Make the request
        response = client.patch(
            f"{self.base_url}/stamps/bulk/meta/compose-db",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data["updated"]) == 2

        assert missing_id not in data["updated"]
        assert ids[0] in data["updated"]
        assert ids[1] in data["updated"]

        assert CeramicCache.objects.filter(compose_db_save_status="saved").count() == 1
        assert CeramicCache.objects.filter(compose_db_save_status="failed").count() == 1
        assert (
            CeramicCache.objects.filter(compose_db_save_status="pending").count() == 1
        )
        assert (
            CeramicCache.objects.filter(compose_db_stream_id="stream-id-1").count() == 1
        )
