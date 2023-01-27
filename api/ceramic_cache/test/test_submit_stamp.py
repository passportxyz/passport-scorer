import json

import pytest
from ceramic_cache.models import CeramicCache
from django.test import Client

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
        stamp=json.dumps(verifiable_credential),
    )

    delete_stamp_response = client.delete(
        "/ceramic-cache/stamp",
        json.dumps(params),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer supersecret",
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
                HTTP_AUTHORIZATION=f"Bearer supersecret",
            )

            responses.append(cache_stamp_response)

        assert responses[0].status_code == 201
        assert responses[0].json()["stamp"] == '{"stamp": 1}'
        assert responses[1].status_code == 201
        assert responses[1].json()["stamp"] == '{"stamp": 2}'

    def test_bad_bearer_token_returns_401(
        self, verifiable_credential, sample_provider, sample_address
    ):
        params = {
            "address": sample_address,
            "provider": sample_provider,
            "stamp": verifiable_credential,
        }

        cache_stamp_response = client.post(
            "/ceramic-cache/stamp",
            json.dumps(params),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer notsecret",
        )

        assert cache_stamp_response.status_code == 401

    def test_soft_delete_stamp(
        self, sample_provider, sample_address, verifiable_credential
    ):
        delete_stamp_response = create_delete_stamp(
            sample_address, sample_provider, verifiable_credential
        )

        assert delete_stamp_response.status_code == 200
        assert delete_stamp_response.json()["status"] == "deleted"
        assert (
            CeramicCache.objects.get(
                address=sample_address, provider=sample_provider
            ).deleted_at
            == True
        )

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
            HTTP_AUTHORIZATION=f"Bearer supersecret",
        )

        assert (
            CeramicCache.objects.get(
                address=sample_address, provider=sample_provider
            ).deleted_at
            == False
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
            HTTP_AUTHORIZATION=f"Bearer supersecret",
        )

        assert delete_stamp_response.status_code == 404
        assert (
            delete_stamp_response.json()["detail"] == "Unable to find stamp to delete."
        )
