from typing import cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import Client, TestCase

from account.models import Account, AccountAPIKey, RateLimits

# Avoids type issues in standard django models
user_manager = cast(UserManager, get_user_model().objects)


class ValidateApiKeyTestCase(TestCase):
    def setUp(self):
        user_manager.create_user(username="admin", password="12345")

        self.user = user_manager.create_user(username="testuser-1", password="12345")

        (self.account, _) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )

        self.client = Client()

    def test_rate_limit_bad_api_key(self):
        """Test that the rate limit API returns error when an invalid API key is provided"""

        rate_limit_response = self.client.get(
            "/internal/embed/validate-api-key",
            **{"HTTP_X-API-KEY": f"api_id.some_api_key"},
        )
        assert rate_limit_response.status_code == 401
        data = rate_limit_response.json()
        assert data == {"detail": "Invalid API Key."}

    def test_rate_limit_success(self):
        """Test that the rate limit API when correct API key is provided"""

        (api_key_obj, api_key) = AccountAPIKey.objects.create_key(
            account=self.account,
            name="Token for user 1",
        )

        rate_limit_response = self.client.get(
            "/internal/embed/validate-api-key",
            **{"HTTP_X-API-KEY": api_key},
        )

        assert rate_limit_response.status_code == 200
        data = rate_limit_response.json()
        assert data == {"rate_limit": api_key_obj.rate_limit}

    def test_rate_limit_success_for_unlimited_rate(self):
        """Test that the rate limit API when the rate limit is set to UNLIMITED"""

        (api_key_obj, api_key) = AccountAPIKey.objects.create_key(
            account=self.account,
            name="Token for user 1",
            rate_limit=RateLimits.UNLIMITED.value,
        )

        rate_limit_response = self.client.get(
            "/internal/embed/validate-api-key",
            **{"HTTP_X-API-KEY": api_key},
        )

        assert rate_limit_response.status_code == 200
        data = rate_limit_response.json()
        assert data == {"rate_limit": api_key_obj.rate_limit}
