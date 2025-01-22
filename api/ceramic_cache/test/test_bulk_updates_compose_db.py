import json

import pytest

from ceramic_cache.models import CeramicCache

pytestmark = pytest.mark.django_db


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
        client,
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
