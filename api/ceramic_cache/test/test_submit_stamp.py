import json

import pytest
from ceramic_cache.models import CeramicCache
from django.test import Client

pytestmark = pytest.mark.django_db

client = Client()


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

    def test_bad_bearer_token_resturns_401(
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
