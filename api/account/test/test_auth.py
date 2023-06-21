import json

from account.models import Account, AccountAPIKey
from django.contrib.auth.models import User
from django.test import Client, TestCase
from ninja_jwt.schema import RefreshToken

mock_api_key_body = {"name": "test"}


class AuthTestCase(TestCase):
    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        User.objects.create_user(username="admin", password="12345")

        self.user = User.objects.create_user(username="testuser-1", password="12345")

        refresh = RefreshToken.for_user(self.user)
        refresh["ip_address"] = "127.0.0.1"
        self.access_token = refresh.access_token

        (self.account, _created) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )

    def test_create_api_key_with_bad_token(self):
        """Test that creation of an API key with bad token fails"""
        client = Client()

        invalid_response = client.post(
            "/account/api-key",
            json.dumps(mock_api_key_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer bad_token"},
        )
        self.assertEqual(invalid_response.status_code, 401)

    def test_ip_change_in_create_api_key(self):
        """Test that creation of an API key fails after IP change"""
        client = Client()
        api_key_response = client.post(
            "/account/api-key",
            json.dumps(mock_api_key_body),
            content_type="application/json",
            **{
                "HTTP_AUTHORIZATION": f"Bearer {self.access_token}",
                "HTTP_X_FORWARDED_FOR": "127.0.0.1",
            },
        )
        self.assertEqual(api_key_response.status_code, 200)

        api_key_response_again = client.post(
            "/account/api-key",
            json.dumps(mock_api_key_body),
            content_type="application/json",
            **{
                "HTTP_AUTHORIZATION": f"Bearer {self.access_token}",
                "HTTP_X_FORWARDED_FOR": "172.1.1.1",
            },
        )
        self.assertEqual(api_key_response_again.status_code, 401)
        self.assertEqual(
            api_key_response_again.json()["detail"], "IP address has changed"
        )

    def test_get_api_keys_with_bad_token(self):
        """Test that getting API keys with bad token fails"""
        client = Client()

        invalid_response = client.get(
            "/account/api-key",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer invalid_token"},
        )
        self.assertEqual(invalid_response.status_code, 401)
