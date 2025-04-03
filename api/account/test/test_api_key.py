import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from ninja_jwt.schema import RefreshToken

from account.models import Account, AccountAPIKey

mock_api_key_body = {"name": "test"}


class ApiKeyTestCase(TestCase):
    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        User.objects.create_user(username="admin", password="12345")

        self.user = User.objects.create_user(username="testuser-1", password="12345")
        self.user2 = User.objects.create_user(username="testuser-2", password="12345")

        refresh = RefreshToken.for_user(self.user)
        refresh["ip_address"] = "127.0.0.1"
        self.access_token = refresh.access_token

        (self.account, _created) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )
        (self.account2, _created) = Account.objects.get_or_create(
            user=self.user2, defaults={"address": "0x0"}
        )

    def test_create_api_key(self):
        """Test that creation of an API key works"""
        client = Client()
        api_key_response = client.post(
            "/account/api-key",
            json.dumps(mock_api_key_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(api_key_response.status_code, 200)

        # Check that the API key was created
        all_api_keys = list(AccountAPIKey.objects.all())
        self.assertEqual(len(all_api_keys), 1)
        self.assertEqual(all_api_keys[0].account.user.username, self.user.username)

    def test_create_api_key_with_duplicate_name(self):
        """Test that creation of an API Key with duplicate name fails"""
        client = Client()
        # create first community
        api_key_response = client.post(
            "/account/api-key",
            json.dumps({"name": "test", "description": "first API key"}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(api_key_response.status_code, 200)

        api_key_response2 = client.post(
            "/account/api-key",
            json.dumps({"name": "test", "description": "another API key"}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(api_key_response2.status_code, 400)

    def test_create_max_api_keys(self):
        """Test that a user is only allowed to create maximum 5 api keys"""
        client = Client()
        for i in range(5):
            api_key_response = client.post(
                "/account/api-key",
                json.dumps({"name": f"test {i}"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )
            self.assertEqual(api_key_response.status_code, 200)

        # check that we are throwing a 401 if they have already created an account
        api_key_response = client.post(
            "/account/api-key",
            json.dumps(mock_api_key_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(api_key_response.status_code, 400)

        # Check that only 5 API keys are in the DB
        all_api_keys = list(AccountAPIKey.objects.all())
        self.assertEqual(len(all_api_keys), 5)

    def test_get_api_keys(self):
        """Test that getting API keys is succefull and that they are correctly filtered for the logged in user"""

        # Create API key for first account
        AccountAPIKey.objects.create_key(account=self.account, name="Token for user 1")

        # Create API key for 2nd account
        AccountAPIKey.objects.create_key(account=self.account2, name="Token for user 2")

        client = Client()
        valid_response = client.get(
            "/account/api-key",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )

        self.assertEqual(valid_response.status_code, 200)
        json_response = valid_response.json()
        self.assertEqual(len(json_response), 1)
        self.assertEqual(json_response[0]["name"], "Token for user 1")

    def test_delete_api_key(self):
        """Test deleting the selected API key"""

        # Create API key for first account
        (account_api_key, secret) = AccountAPIKey.objects.create_key(
            account=self.account, name="Token for user 1"
        )

        AccountAPIKey.objects.create_key(
            account=self.account2, name="Another token for user 1"
        )

        client = Client()

        valid_response = client.delete(
            f"/account/api-key/{account_api_key.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(valid_response.status_code, 200)
        data = valid_response.json()
        self.assertTrue("ok" in data)

        # Check that the object was deleted in the DB
        all_api_keys = list(AccountAPIKey.objects.all())
        self.assertEqual(len(all_api_keys), 1)
        self.assertEqual(all_api_keys[0].name, "Another token for user 1")

    def test_delete_api_key_with_slash_in_id(self):
        """Test deleting the selected API key"""

        # Create API key for first account
        (account_api_key, secret) = AccountAPIKey.objects.create_key(
            account=self.account,
            name="Token for user 2",
        )

        modified_api_key = account_api_key.id.replace(account_api_key.id[0:3], "ABC")
        modified_prefix = modified_api_key.split(".")[0]

        # Forcefully add a "/"
        account_api_key.id = f"{modified_api_key}/SJF"
        account_api_key.prefix = modified_prefix

        account_api_key.save()

        client = Client()

        valid_response = client.delete(
            f"/account/api-key/{account_api_key.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(valid_response.status_code, 200)
        data = valid_response.json()
        self.assertTrue("ok" in data)

        # Check that the object was deleted in the DB
        all_api_keys = list(AccountAPIKey.objects.all())
        self.assertEqual(len(all_api_keys), 1)
        # Make sure the API key was deleted
        self.assertEqual(AccountAPIKey.objects.filter(pk=account_api_key.id).count(), 0)

    def test_successful_patch_api_key(self):
        client = Client()
        # Create API key for first account
        (account_api_key, secret) = AccountAPIKey.objects.create_key(
            account=self.account, name="Token for user 1"
        )

        valid_response = client.patch(
            f"/account/api-key/{account_api_key.id}",
            json.dumps(mock_api_key_body),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(valid_response.status_code, 200)

    def test_successful_patch_invalid_api_key(self):
        client = Client()
        # Create API key for first account
        (account_api_key, secret) = AccountAPIKey.objects.create_key(
            account=self.account, name="Token for user 1"
        )

        valid_response = client.patch(
            "/account/api-key/bad-key",
            json.dumps(mock_api_key_body),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(valid_response.status_code, 404)
