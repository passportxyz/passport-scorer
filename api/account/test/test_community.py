from django.test import TestCase
from django.test import Client

# Create your tests here.

import json
from .authenticate import authenticate

mock_api_key_body = {"name": "test"}
mock_community_body = {"name": "test", "description": "test"}


class AccountTestCase(TestCase):
    def setUp(self):
        pass

    def test_create_community(self):
        """Test creation of a community"""
        client = Client()
        response, account, signed_message = authenticate(client)
        access_token = response.json()["access"]

        invalid_response = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer invalid_token"},
        )
        self.assertEqual(invalid_response.status_code, 401)

        valid_response = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {access_token}"},
        )
        self.assertEqual(valid_response.status_code, 200)

        duplicate_community = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {access_token}"},
        )
        self.assertEqual(duplicate_community.status_code, 401)

        # Check too many communities
        for i in range(0, 4):
            client.post(
                "/account/communities",
                json.dumps({"name": f"test{i}"}),
                content_type="application/json",
                **{"HTTP_AUTHORIZATION": f"Bearer {access_token}"},
            )

        too_many_communities = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {access_token}"},
        )
        self.assertEqual(too_many_communities.status_code, 401)

    def test_get_communities(self):
        """Test getting communities"""
        client = Client()
        response, account, signed_message = authenticate(client)
        access_token = response.json()["access"]

        invalid_response = client.get(
            "/account/communities",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer invalid_token"},
        )
        self.assertEqual(invalid_response.status_code, 401)

        valid_response = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {access_token}"},
        )

        valid_response = client.get(
            "/account/communities",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {access_token}"},
        )
        self.assertEqual(valid_response.status_code, 200)

        json_response = valid_response.json()
        self.assertTrue("description" in json_response[0])
        self.assertTrue("name" in json_response[0])
