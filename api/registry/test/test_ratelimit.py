import json
import logging
from unittest.mock import patch

import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db

log = logging.getLogger(__name__)


@override_settings(RATELIMIT_ENABLE=True)
def test_rate_limit_is_applyed(scorer_api_key):
    """Make sure the rate limit set in the account is applied when calling the APIs"""

    client = Client()
    # The lowest default limit is set to 125/15m, so we expect to be able to make
    # 125 successfull calls, and then get a 429 error
    for _ in range(125):
        response = client.get(
            "/registry/signing-message",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 200

    response = client.get(
        "/registry/signing-message",
        HTTP_AUTHORIZATION="Token " + scorer_api_key,
    )

    assert response.status_code == 429


# Ensure that all functions that rquire rate limiting are tested
@pytest.fixture(
    params=[
        ("get", "/registry/signing-message", None),
        (
            "post",
            "/registry/submit-passport",
            {
                "community": "1",
                "address": "0x1234",
            },
        ),
        ("get", "/registry/score/3", None),
    ]
)
def api_path_that_requires_rate_limit(request):
    return request.param


@override_settings(RATELIMIT_ENABLE=True)
def test_rate_limit_is_applied(scorer_api_key, api_path_that_requires_rate_limit):
    """
    Test that api rate limit is applied for all required APIs.
    """
    method, path, payload = api_path_that_requires_rate_limit
    client = Client()

    with patch("registry.api.is_ratelimited", return_value=True):
        if method == "post":
            response = client.post(
                path,
                json.dumps(payload),
                **{
                    "content_type": "application/json",
                    "HTTP_AUTHORIZATION": f"Token {scorer_api_key}",
                },
            )
            assert response.status_code == 429
        else:
            response = client.get(
                path,
                HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
            )
            assert response.status_code == 429
