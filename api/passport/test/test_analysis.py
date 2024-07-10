import json
from unittest.mock import Mock, patch

import pytest
from account.models import Account, AccountAPIKey
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from passport.api import MODEL_ENDPOINTS
from web3 import Web3

pytestmark = pytest.mark.django_db

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


def mock_post_response(url, json, headers):
    # Create a mock response object
    mock_response = Mock()
    mock_response.status_code = 200

    # Define different responses based on the model (which we can infer from the URL)
    responses = {
        "ethereum": {
            "data": {"human_probability": 75},
            "metadata": {"model_name": "ethereum_activity", "version": "1.0"},
        },
    }

    # Determine which model is being requested
    for model, endpoint in MODEL_ENDPOINTS.items():
        if endpoint in url:
            response_data = responses.get(model, {"data": {"human_probability": 0}})
            break
    else:
        response_data = {"error": "Unknown model"}

    # Set the json method of the mock response
    mock_response.json = lambda: response_data

    return mock_response


@pytest.mark.django_db
class TestPassportAnalysis(TestCase):
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
        self.client = Client()

    @patch("requests.post", side_effect=mock_post_response)
    def test_get_analysis_request(self, mock_post):
        """Test successfully requesting analysis through the API."""

        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D?model_list=ethereum",
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(analysis_response.status_code, 200)

        response_data = analysis_response.json()
        self.assertEqual(
            response_data["address"], "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D"
        )
        self.assertEqual(response_data["details"]["models"]["ethereum"], {"score": 75})

    def test_bad_auth(self):
        headers = {"HTTP_X-API-Key": "bad_auth"}
        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D?model_list=ethereum",
            content_type="application/json",
            **headers,
        )

        self.assertEqual(analysis_response.status_code, 401)

    def test_bad_address(self):
        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7d?model_list=ethereum",
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(analysis_response.status_code, 400)
