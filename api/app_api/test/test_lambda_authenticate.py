import json
from typing import cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import TestCase

from app_api.lambda_fn import lambda_handler_authenticate
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext

# Avoids type issues in standard django models
user_manager = cast(UserManager, get_user_model().objects)


class AuthenticateLambdaTestCase(TestCase):
    def setUp(self):
        pass

    @patch("app_api.lambda_fn.close_old_connections", side_effect=[None])
    def test_authenticate_options(self, close_old_connections):
        """Test that the CORS request is returning proper headers"""

        event = {
            "headers": {},
            "path": "/ceramic-cache/authenticate",
            "isBase64Encoded": False,
            "body": "",
            "httpMethod": "OPTIONS",
        }

        result = lambda_handler_authenticate(event, MockContext())

        assert result == {
            "headers": {
                "Access-Control-Allow-Methods": "POST,OPTIONS",
                "Access-Control-Allow-Headers": "Accept,Accept-Encoding,Authorization,Content-Type,Dnt,Origin,User-Agent,X-Csrftoken,X-Requested-With,X-Api-Key",
                "Access-Control-Allow-Origin": "*",
                "Cross-Origin-Opener-Policy": "same-origin",
                "Content-Type": "application/json",
            },
            "statusCode": 200,
            "body": "",  # Empty body for OPTIONS request
        }
        assert close_old_connections.call_count == 1
