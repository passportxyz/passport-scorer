from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from web3 import Web3

from account.models import Account, AccountAPIKey
from aws_lambdas.passport.tests.test_passport_analysis_lambda import mock_post_response

pytestmark = pytest.mark.django_db

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC

User = get_user_model()


@pytest.mark.django_db
class TestPassportAnalysis(TestCase):
    def setUp(self):
        user = User.objects.create(username="admin", password="12345")

        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )

        user_account = Account.objects.create(user=user, address=account.address)

        _obj, api_key = AccountAPIKey.objects.create_key(
            account=user_account,
            name="Token for user 1",
            analysis_rate_limit="100/30seconds",
        )

        self.headers = {"HTTP_X-API-Key": f"{api_key}"}
        self.client = Client()

    @patch("passport.api.fetch", side_effect=mock_post_response)
    def test_get_analysis_request(self, mock_post):
        """Test successfully requesting analysis through the API."""

        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D?model_list=ethereum_activity",
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(analysis_response.status_code, 200)
        self.assertEqual(
            analysis_response.json(),
            {
                "address": "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                "details": {"models": {"ethereum_activity": {"score": 75}}},
            },
        )

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
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7d",
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(analysis_response.status_code, 400)

    @override_settings(RATELIMIT_ENABLE=True)
    def test_rate_limit_is_applied(self):
        """
        Test that api rate limit is applied
        """
        client = Client()

        with patch("registry.api.utils.is_ratelimited", return_value=True):
            response = client.get(
                "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                **self.headers,
            )
            assert response.status_code == 429

    @patch("passport.api.fetch", side_effect=mock_post_response)
    def test_checksummed_address_is_passed_on(self, mock_post):
        """
        It is a requirement that the checksummed address is passed on in the requests to the model APIs.
        This is not enforced in the models.
        Changing this would affect the current cached values
        """
        self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7d".lower(),
            content_type="application/json",
            **self.headers,
        )

        # Verify that the address passed on is the checksummed address
        assert mock_post.call_args.args[2] == {
            "address": "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D"
        }
