from typing import cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import Client, TestCase

from account.models import Account, AccountAPIKey, EmbedRateLimits
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext
from embed.lambda_fn import lambda_handler_get_rate_limit

# Avoids type issues in standard django models
user_manager = cast(UserManager, get_user_model().objects)


class ValidateLambdaValidateApiKeyTestCase(TestCase):
    def setUp(self):
        user_manager.create_user(username="admin", password="12345")

        self.user = user_manager.create_user(username="testuser-1", password="12345")

        (self.account, _) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )

        self.client = Client()

    @patch("embed.lambda_fn.close_old_connections", side_effect=[None])
    def test_rate_limit_bad_api_key(self, _close_old_connections):
        """Test that the rate limit API returns error when an invalid API key is provided"""

        event = {
            "headers": {"x-api-key": "api_id.some_api_key"},
            "path": "/embed/validate-api-key",
            "isBase64Encoded": False,
        }

        result = lambda_handler_get_rate_limit(event, MockContext())

        assert result == {
            "body": '{"detail": "Invalid API Key."}',
            "headers": {
                "Access-Control-Allow-Headers": "Accept,Accept-Encoding,Authorization,Content-Type,Dnt,Origin,User-Agent,X-Csrftoken,X-Requested-With,X-Api-Key",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json",
            },
            "statusCode": 401,
            "statusCategory": "4XX",
            "isBase64Encoded": False,
            "statusDescription": "Invalid API Key.",
        }
        assert _close_old_connections.call_count == 1

    @patch("embed.lambda_fn.close_old_connections", side_effect=[None])
    def test_rate_limit_success(self, _close_old_connections):
        """Test that the rate limit API when correct API key is provided"""

        (api_key_obj, api_key) = AccountAPIKey.objects.create_key(
            account=self.account,
            name="Token for user 1",
        )

        event = {
            "headers": {"x-api-key": api_key},
            "path": "/embed/validate-api-key",
            "isBase64Encoded": False,
        }

        result = lambda_handler_get_rate_limit(event, MockContext())

        assert result == {
            "body": '{"embed_rate_limit":"0/15m"}',
            "headers": {"Content-Type": "application/json"},
            "statusCode": 200,
        }
        assert _close_old_connections.call_count == 1

    @patch("embed.lambda_fn.close_old_connections", side_effect=[None])
    def test_rate_limit_success(self, _close_old_connections):
        """Test that the rate limit API when correct API key is provided"""

        (api_key_obj, api_key) = AccountAPIKey.objects.create_key(
            account=self.account,
            name="Token for user 1",
            embed_rate_limit=EmbedRateLimits.UNLIMITED.value,
        )

        event = {
            "headers": {"x-api-key": api_key},
            "path": "/embed/validate-api-key",
            "isBase64Encoded": False,
        }

        result = lambda_handler_get_rate_limit(event, MockContext())

        assert result == {
            "body": '{"embed_rate_limit":""}',
            "headers": {"Content-Type": "application/json"},
            "statusCode": 200,
        }
        assert _close_old_connections.call_count == 1
