import json
from typing import cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import TestCase
from ninja_extra.exceptions import ValidationError

from app_api.lambda_fn import lambda_handler_authenticate
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext
from ceramic_cache.api.schema import AccessTokenResponse

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

    @patch("app_api.lambda_fn.close_old_connections", side_effect=[None])
    @patch(
        "app_api.lambda_fn.handle_authenticate",
        return_value=AccessTokenResponse(access="access", intercom_user_hash="hash"),
    )
    def test_authenticate_success(self, handle_authenticate, close_old_connections):
        """Test that the CORS request is returning proper headers"""

        event = {
            "headers": {},
            "path": "/ceramic-cache/authenticate",
            "isBase64Encoded": False,
            "body": json.dumps(
                {
                    "issuer": "issuer",
                    "signatures": [{"some": "sig"}],
                    "nonce": "nonce",
                    "payload": "payload",
                    "cid": [1, 2],
                    "cacao": [3, 4],
                }
            ),
            "httpMethod": "POST",
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
            "body": '{"access":"access","intercom_user_hash":"hash"}',
        }
        assert close_old_connections.call_count == 1
        assert handle_authenticate.call_count == 1

    @patch("app_api.lambda_fn.close_old_connections", side_effect=[None])
    @patch(
        "app_api.lambda_fn.handle_authenticate",
        side_effect=[ValidationError(detail="Bad test credentials")],
    )
    def test_authenticate_failure(self, handle_authenticate, close_old_connections):
        """Test that the CORS request is returning proper headers"""

        event = {
            "headers": {},
            "path": "/ceramic-cache/authenticate",
            "isBase64Encoded": False,
            "body": json.dumps(
                {
                    "issuer": "issuer",
                    "signatures": [{"some": "sig"}],
                    "nonce": "nonce",
                    "payload": "payload",
                    "cid": [1, 2],
                    "cacao": [3, 4],
                }
            ),
            "httpMethod": "POST",
        }

        result = lambda_handler_authenticate(event, MockContext())

        assert result == {
            "headers": {
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "Accept,Accept-Encoding,Authorization,Content-Type,Dnt,Origin,User-Agent,X-Csrftoken,X-Requested-With,X-Api-Key",
                "Access-Control-Allow-Origin": "*",
                "Cross-Origin-Opener-Policy": "same-origin",
                "Content-Type": "application/json",
            },
            "statusCode": 400,
            "statusCategory": "4XX",
            "body": json.dumps(
                {
                    "detail": "[ErrorDetail(string='Bad test credentials', code='invalid')]"
                }
            ),
            "isBase64Encoded": False,
            "statusDescription": "[ErrorDetail(string='Bad test credentials', code='invalid')]",
        }
        assert close_old_connections.call_count == 1
        assert handle_authenticate.call_count == 1
