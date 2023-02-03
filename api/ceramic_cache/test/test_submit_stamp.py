import json

import pytest
from ceramic_cache.models import CeramicCache
from django.test import Client
from datetime import datetime

pytestmark = pytest.mark.django_db

client = Client()


def create_delete_stamp(sample_address, sample_provider, verifiable_credential):
    params = {
        "address": sample_address,
        "provider": sample_provider,
    }

    CeramicCache.objects.create(
        address=sample_address,
        provider=sample_provider,
        stamp=verifiable_credential,
    )

    delete_stamp_response = client.delete(
        "/ceramic-cache/stamp",
        json.dumps(params),
        content_type="application/json",
        **{"HTTP_X_API_KEY": "supersecret"},
    )

    return delete_stamp_response


class TestSubmitStamp:
    def test_updated_stamp_is_saved_to_address_provider_record(
        self, sample_provider, sample_address
    ):
        params = {
            "address": sample_address,
            "provider": sample_provider,
        }

        responses = []
        for i in range(1, 3):
            params["stamp"] = json.dumps({"stamp": i})

            cache_stamp_response = client.post(
                "/ceramic-cache/stamp",
                json.dumps(params),
                content_type="application/json",
                **{"HTTP_X_API_KEY": "supersecret"},
            )

            responses.append(cache_stamp_response)

        assert responses[0].status_code == 201
        assert responses[0].json()["stamp"] == '{"stamp": 1}'
        assert responses[1].status_code == 201
        assert responses[1].json()["stamp"] == '{"stamp": 2}'

    def test_soft_delete_stamp(
        self, mocker, sample_provider, sample_address, verifiable_credential
    ):
        mocker.patch(
            "ceramic_cache.api.get_utc_time",
            return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
        )
        delete_stamp_response = create_delete_stamp(
            sample_address, sample_provider, verifiable_credential
        )

        assert delete_stamp_response.status_code == 200
        assert delete_stamp_response.json()["status"] == "deleted"
        assert CeramicCache.objects.get(
            address=sample_address, provider=sample_provider
        ).deleted_at == datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00")

    def test_recreate_soft_deleted_stamp(
        self, sample_provider, sample_address, verifiable_credential
    ):
        delete_stamp_response = create_delete_stamp(
            sample_address, sample_provider, verifiable_credential
        )

        params = {
            "address": sample_address,
            "provider": sample_provider,
            "stamp": verifiable_credential,
        }

        cache_stamp_response = client.post(
            "/ceramic-cache/stamp",
            json.dumps(params),
            content_type="application/json",
            **{"HTTP_X_API_KEY": "supersecret"},
        )

        assert (
            CeramicCache.objects.get(
                address=sample_address, provider=sample_provider
            ).deleted_at
            == None
        )

    def test_soft_delete_non_existent_record(self, sample_provider, sample_address):
        params = {
            "address": sample_address,
            "provider": sample_provider,
        }

        delete_stamp_response = client.delete(
            "/ceramic-cache/stamp",
            json.dumps(params),
            content_type="application/json",
            **{"HTTP_X_API_KEY": "supersecret"},
        )

        assert delete_stamp_response.status_code == 404
        assert (
            delete_stamp_response.json()["detail"] == "Unable to find stamp to delete."
        )
