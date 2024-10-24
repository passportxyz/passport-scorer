from unittest.mock import Mock, patch

import pytest
from django.test import Client, override_settings

import api_logging as logging

pytestmark = pytest.mark.django_db

log = logging.getLogger(__name__)


@override_settings(FF_API_ANALYTICS="on")
def test_analytics_saved_for_successful_request(scorer_api_key):
    """
    Test that analytics data is saved correctly for successful API requests
    """
    client = Client()

    with patch(
        "account.models.AccountAPIKeyAnalytics.objects.create", new=Mock()
    ) as mock_analytics:
        response = client.get(
            "/registry/signing-message",
            **{"HTTP_X_API_KEY": scorer_api_key},
        )

        assert response.status_code == 200

        # Verify analytics were saved with correct data
        mock_analytics.assert_called_once()
        call_kwargs = mock_analytics.call_args[1]

        assert call_kwargs["path"] == "/registry/signing-message"
        assert call_kwargs["path_segments"] == ["registry", "signing-message"]
        assert call_kwargs["error"] is None
        assert call_kwargs["status_code"] is 200


@override_settings(FF_API_ANALYTICS="on", RATELIMIT_ENABLE=True)
def test_analytics_saved_for_rate_limited_request(scorer_api_key):
    """
    Test that analytics data is saved correctly when API requests fail
    """
    client = Client()

    # Make too many requests to trigger rate limit error
    for _ in range(4):
        client.get("/registry/signing-message", **{"HTTP_X_API_KEY": scorer_api_key})

    with patch(
        "account.models.AccountAPIKeyAnalytics.objects.create", new=Mock()
    ) as mock_analytics:
        response = client.get(
            "/registry/signing-message",
            **{"HTTP_X_API_KEY": scorer_api_key},
        )

        assert response.status_code == 429

        # Verify analytics were saved with error information
        mock_analytics.assert_called_once()
        call_kwargs = mock_analytics.call_args[1]

        assert call_kwargs["path"] == "/registry/signing-message"
        assert call_kwargs["status_code"] == 429


@override_settings(FF_API_ANALYTICS="on", RATELIMIT_ENABLE=True)
def test_analytics_saved_for_unauthorized_request(scorer_api_key):
    """
    Test that analytics data is saved correctly when API requests fail
    """
    client = Client()

    with patch(
        "account.models.AccountAPIKeyAnalytics.objects.create", new=Mock()
    ) as mock_analytics:
        response = client.get(
            "/registry/signing-message",
            **{"HTTP_X_API_KEY": "bad key"},
        )

        assert response.status_code == 401

        # Verify analytics were saved with error information
        mock_analytics.assert_called_once()
        call_kwargs = mock_analytics.call_args[1]

        assert call_kwargs["path"] == "/registry/signing-message"
        assert call_kwargs["status_code"] == 401
