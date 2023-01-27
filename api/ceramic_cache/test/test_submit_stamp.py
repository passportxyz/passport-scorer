import json

import pytest
from ceramic_cache.models import CeramicCache

from django.test import Client

pytestmark = pytest.mark.django_db


class TestSubmitStamp:
    def test_duplicate_stamp(
        self, verifiable_credential, sample_provider, sample_address
    ):
        params = {
            "address": sample_address,
            "provider": sample_provider,
            "stamp": verifiable_credential,
        }

        responses = []
        for i in range(1, 2):
            client = Client()
            cache_stamp_response = client.post(
                "/ceramic-cache/stamp",
                json.dumps(params),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer supersecret",
            )

            responses.append(cache_stamp_response)

        assert responses[0]["status_code"] == 201
        assert responses[1]["status_code"] == 403
