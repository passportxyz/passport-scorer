import json
from unittest.mock import patch

import pytest
from django.test import Client, override_settings

import api_logging as logging
from account.models import AccountAPIKey, RateLimits

pytestmark = pytest.mark.django_db

log = logging.getLogger(__name__)


@pytest.fixture
def unlimited_scorer_api_key(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account,
        name="Token for user 1",
        rate_limit=RateLimits.UNLIMITED.value,
    )
    return secret


@override_settings(RATELIMIT_ENABLE=True)
def test_rate_limit_from_db_is_applied_for_api_key(scorer_api_key):
    """
    Make sure the rate limit set in the account is applied when calling the APIs
    When using the x-api-key header
    """

    client = Client()
    # The lowest default limit is set to 125/15m, so we expect to be able to make
    # 125 successfull calls, and then get a 429 error
    for _ in range(3):
        response = client.get(
            "/registry/signing-message",
            # HTTP_X_API_KEY must spelled exactly as this because it
            # will not be converted to HTTP_X_API_KEY by Django Test Client
            **{"HTTP_X_API_KEY": scorer_api_key},
        )

        assert response.status_code == 200

    response = client.get(
        "/registry/signing-message",
        # HTTP_X_API_KEY must spelled exactly as this because it
        # will not be converted to HTTP_X_API_KEY by Django Test Client
        **{"HTTP_X_API_KEY": scorer_api_key},
    )

    assert response.status_code == 429

    address = "0xd49e5a2c0EF6ca8B5A826c93e1c4720026da565D"

    # make sure doesn't interfere with analytics rate limit
    with patch(
        "passport.api.handle_get_analysis",
        return_value={
            "address": address,
            "details": {"models": {"ethereum_activity": {"score": 0.5}}},
        },
    ):
        response = client.get(
            f"/passport/analysis/{address}",
            **{
                "HTTP_X_API_KEY": scorer_api_key,
            },
        )

        assert response.status_code == 200


@override_settings(RATELIMIT_ENABLE=True)
def test_rate_limit_from_db_is_applied_for_token(scorer_api_key):
    """
    Make sure the rate limit set in the account is applied when calling the APIs
    When using the HTTP_AUTHORIZATION header
    """

    client = Client()
    # The rate limit is overridden to 3 calls/30 seconds for this APIKey
    for _ in range(3):
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

    with patch("registry.api.utils.is_ratelimited", return_value=True):
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


@override_settings(RATELIMIT_ENABLE=True)
def test_no_rate_limit_for_none(unlimited_scorer_api_key):
    """
    Test that no rate limit is applied when rate_limit is set to None.
    """
    client = Client()
    # The rate limit is overridden to 3 calls/30 seconds for this APIKey
    for _ in range(3):
        response = client.get(
            "/registry/signing-message",
            HTTP_AUTHORIZATION="Token " + unlimited_scorer_api_key,
        )

        assert response.status_code == 200

    response = client.get(
        "/registry/signing-message",
        HTTP_AUTHORIZATION="Token " + unlimited_scorer_api_key,
    )

    assert response.status_code == 200
