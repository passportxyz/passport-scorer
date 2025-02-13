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

    @patch("app_api.lambda_fn.close_old_connections", side_effect=[None])
    def test_nonce_returned(self, _close_old_connections):
        """Test that a new nonce is returned"""

        event = {
            "headers": {},
            "path": "/account/nonce",
            "isBase64Encoded": False,
            "body": "",
            "httpMethod": "GET",
        }

        result = lambda_handler_account_nonce(event, MockContext())

        nonce = Nonce.objects.all()[0]

        assert result == {
            "headers": {
                "Access-Control-Allow-Methods": "GET,OPTIONS",
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json",
                "Cross-Origin-Opener-Policy": "same-origin",
                "Access-Control-Allow-Headers": "Accept,Accept-Encoding,Authorization,Content-Type,Dnt,Origin,User-Agent,X-Csrftoken,X-Requested-With,X-Api-Key",
            },
            "statusCode": 200,
            "body": json.dumps({"nonce": nonce.nonce}),
        }
        assert _close_old_connections.call_count == 1

    @patch("app_api.lambda_fn.close_old_connections", side_effect=[None])
    def test_nonce_options(self, _close_old_connections):
        """Test that the CORS request is returning proper headers"""

        event = {
            "headers": {},
            "path": "/account/nonce",
            "isBase64Encoded": False,
            "body": "",
            "httpMethod": "OPTIONS",
        }

        nonce_count = len(Nonce.objects.all())

        result = lambda_handler_account_nonce(event, MockContext())

        assert result == {
            "headers": {
                "Access-Control-Allow-Methods": "GET,OPTIONS",
                "Access-Control-Allow-Origin": "*",
                "Cross-Origin-Opener-Policy": "same-origin",
                "Access-Control-Allow-Headers": "Accept,Accept-Encoding,Authorization,Content-Type,Dnt,Origin,User-Agent,X-Csrftoken,X-Requested-With,X-Api-Key",
                "Content-Type": "application/json",
            },
            "statusCode": 200,
            "body": "",  # Empty body for OPTIONS request
        }
        assert nonce_count == 0
        assert _close_old_connections.call_count == 1
