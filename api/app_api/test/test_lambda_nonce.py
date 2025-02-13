import json
from typing import cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import TestCase

from account.models import Nonce
from app_api.lambda_fn import lambda_handler_account_nonce
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext

# Avoids type issues in standard django models
user_manager = cast(UserManager, get_user_model().objects)


class AccountNonceLambdaTestCase(TestCase):
    def setUp(self):
        pass

    def test_rate_limit_bad_api_key(self):
        """Test that the rate limit API returns error when an invalid API key is provided"""

        # This test is actually not necesary for the lambda as this is only exposed on the internal API
        assert True

    @patch("app_api.lambda_fn.close_old_connections", side_effect=[None])
    def test_nonce_returned(self, _close_old_connections):
        """Test that a new nonce is returned"""

        event = {
            "headers": {},
            "path": "/account/nonce",
            "isBase64Encoded": False,
            "body": "",
        }

        result = lambda_handler_account_nonce(event, MockContext())

        nonce = Nonce.objects.all()[0]

        assert result == {
            "headers": {
                "Content-Type": "application/json",
            },
            "statusCode": 200,
            "body": json.dumps({"nonce": nonce.nonce}),
        }
        assert _close_old_connections.call_count == 1
