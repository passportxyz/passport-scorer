from unittest.mock import MagicMock, patch

import pytest
from account.models import AccountAPIKey, AccountAPIKeyAnalytics
from registry.tasks import save_api_key_analytics


@pytest.mark.django_db
class TestSaveApiKeyAnalytics:
    def test_save_api_key_analytics_new_analytics(self, scorer_account):
        path = "/test_path/"

        (model, secret) = AccountAPIKey.objects.create_key(
            account=scorer_account, name="Another token for user 1"
        )

        save_api_key_analytics(secret, path)

        analytics, created = AccountAPIKeyAnalytics.objects.get_or_create(
            api_key=model, path=path
        )

        assert analytics.request_count == 1

    def test_save_api_key_analytics_increments_count(self, scorer_account):
        path = "/test_path/"

        (model, secret) = AccountAPIKey.objects.create_key(
            account=scorer_account, name="Another token for user 1"
        )

        save_api_key_analytics(secret, path)
        save_api_key_analytics(secret, path)

        analytics, created = AccountAPIKeyAnalytics.objects.get_or_create(
            api_key=model, path=path
        )

        assert analytics.request_count == 2

    def test_save_api_key_analytics_does_not_increment_count_for_different_path(
        self, scorer_account
    ):
        path = "/test_path/"

        (model, secret) = AccountAPIKey.objects.create_key(
            account=scorer_account, name="Another token for user 1"
        )

        save_api_key_analytics(secret, path)
        save_api_key_analytics(secret, "/new_path")

        analytics, created = AccountAPIKeyAnalytics.objects.get_or_create(
            api_key=model, path=path
        )

        assert analytics.request_count == 1

    def test_invalid_secret(self, scorer_account):
        path = "/test_path/"

        (model, secret) = AccountAPIKey.objects.create_key(
            account=scorer_account, name="Another token for user 1"
        )

        save_api_key_analytics("secret", path)

        analytics, created = AccountAPIKeyAnalytics.objects.get_or_create(
            api_key=model, path=path
        )

        assert analytics.request_count == 0
        assert created == True
