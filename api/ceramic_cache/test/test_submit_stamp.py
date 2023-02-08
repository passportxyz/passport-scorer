import json

import pytest
from ceramic_cache.models import CeramicCache
from django.test import Client
from datetime import datetime

pytestmark = pytest.mark.django_db

client = Client()


def create_delete_stamp(
    sample_address, sample_provider, verifiable_credential, sample_token
):
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
        **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
    )

    return delete_stamp_response


class TestSubmitStamp:
    def test_updated_stamp_is_saved_to_address_provider_record(
        self, sample_provider, sample_address, sample_token
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
                **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
            )

            responses.append(cache_stamp_response)

        assert responses[0].status_code == 201
        assert responses[0].json()["stamp"] == '{"stamp": 1}'
        assert responses[1].status_code == 201
        assert responses[1].json()["stamp"] == '{"stamp": 2}'

    def test_delete_stamp(
        self,
        mocker,
        sample_provider,
        sample_address,
        verifiable_credential,
        sample_token,
    ):
        delete_stamp_response = create_delete_stamp(
            sample_address, sample_provider, verifiable_credential, sample_token
        )

        assert delete_stamp_response.status_code == 200
        assert delete_stamp_response.json()["status"] == "deleted"
        assert (
            CeramicCache.objects.filter(
                address=sample_address, provider=sample_provider
            ).count()
            == 0
        )

    def test_recreate_deleted_stamp(
        self, sample_provider, sample_address, verifiable_credential, sample_token
    ):
        delete_stamp_response = create_delete_stamp(
            sample_address, sample_provider, verifiable_credential, create_delete_stamp
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
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert (
            CeramicCache.objects.get(
                address=sample_address, provider=sample_provider
            ).provider
            == sample_provider
        )

    def test_delete_non_existent_record(
        self, sample_provider, sample_address, sample_token
    ):
        params = {
            "address": sample_address,
            "provider": sample_provider,
        }

        delete_stamp_response = client.delete(
            "/ceramic-cache/stamp",
            json.dumps(params),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert delete_stamp_response.status_code == 404
        assert (
            delete_stamp_response.json()["detail"] == "Unable to find stamp to delete."
        )
