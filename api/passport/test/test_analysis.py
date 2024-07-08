import json
from unittest.mock import patch

from account.models import Account, AccountAPIKey
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC

User = get_user_model()

mock_response_data = json.dumps(
    {
        "body": json.dumps(
            {
                "data": {
                    "human_probability": 50,
                }
            }
        )
    }
)


class MockPayload:
    def read(self):
        return mock_response_data.encode("utf-8")


class MockLambdaClient:
    def invoke(self, FunctionName, InvocationType, Payload):
        return {"Payload": MockPayload()}


class PassportAnalysisTestCase(TestCase):
    def setUp(self):
        user = User.objects.create(username="admin", password="12345")

        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )

        user_account = Account.objects.create(user=user, address=account.address)

        _obj, api_key = AccountAPIKey.objects.create_key(
            account=user_account, name="Token for user 1"
        )

        self.headers = {"HTTP_X-API-Key": f"{api_key}"}

    def test_get_analysis_request(self):
        """Test successfully requesting analysis through the API."""

        client = Client()

        with patch(
            "passport.api.get_lambda_client",
            MockLambdaClient,
        ):
            analysis_response = client.get(
                "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                content_type="application/json",
                **self.headers,
            )

        self.assertEqual(analysis_response.status_code, 200)
        self.assertEqual(
            analysis_response.json(),
            {
                "address": "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                "details": {"models": {"ethereum_activity": {"score": 50}}},
            },
        )

    def test_bad_auth(self):
        headers = {"HTTP_X-API-Key": "bad_auth"}
        client = Client()

        analysis_response = client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
            content_type="application/json",
            **headers,
        )

        self.assertEqual(analysis_response.status_code, 401)

    def test_bad_address(self):
        client = Client()

        analysis_response = client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7d",
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(analysis_response.status_code, 400)
