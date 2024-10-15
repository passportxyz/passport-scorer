from datetime import datetime

import pytest

from account.models import AccountAPIKey, AccountAPIKeyAnalytics
from registry.tasks import save_api_key_analytics

path = "/test_path/"


@pytest.mark.django_db
class TestSaveApiKeyAnalytics:
    def test_save_api_key_analytics_new_analytics(self, scorer_account):
        (model, secret) = AccountAPIKey.objects.create_key(
            account=scorer_account, name="Another token for user 1"
        )

        save_api_key_analytics(
            model.pk,
            path,
            ["a", "b", "c"],
            {"param1": "value1"},
            {"header": "field1"},
            {"data": "hello"},
            {"response": "reponse content"},
            response_skipped=False,
            error="big problem",
        )

        obj = AccountAPIKeyAnalytics.objects.get(path=path, api_key_id=model.pk)

        created_at_day = datetime.fromisoformat(obj.created_at.isoformat())

        assert created_at_day.day is datetime.now().day
        assert created_at_day.month is datetime.now().month
