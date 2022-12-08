from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User
from ninja_jwt.schema import RefreshToken

import json

from account.models import Account, Community

mock_community_body = {"name": "test", "description": "test"}

class CommunityTestCase(TestCase):
    def setUp(self):
        User.objects.create_user(username="admin", password="12345")

        self.user = User.objects.create_user(username="testuser-1", password="12345")
        self.user2 = User.objects.create_user(username="testuser-2", password="12345")

        refresh = RefreshToken.for_user(self.user)
        self.access_token = refresh.access_token

        (self.account, _created) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )
        (self.account2, _created) = Account.objects.get_or_create(
            user=self.user2, defaults={"address": "0x0"}
        )
    def test_create_community_with_bad_token(self):
        """Test that creation of a community with bad token fails"""
        client = Client()

        invalid_response = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer bad_token"},
        )
        self.assertEqual(invalid_response.status_code, 401)

    def test_create_community(self):
        """Test that creation of a community works"""
        client = Client()
        community_response = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)

        # Check that the community was created
        all_communities = list(Community.objects.all())
        self.assertEqual(len(all_communities), 1)
        self.assertEqual(all_communities[0].account.user.username, self.user.username)

    def test_create_community_with_no_name(self):
        """Test that creation of a community with no name fails"""
        client = Client()
        community_response = client.post(
            "/account/communities",
            json.dumps({"description": "test"}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 422)

    def test_create_community_with_duplicate_name(self):
        """Test that creation of a community with duplicate name fails"""
        client = Client()
        # create first community
        community_response = client.post(
            "/account/communities",
            json.dumps({"name": "test", "description": "first community"}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)

        community_response1 = client.post(
            "/account/communities",
            json.dumps({"name": "test", "description": "another community"}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response1.status_code, 400)
    
    def test_create_community_with_no_description(self):
        """Test that creation of a community with no description fails"""
        client = Client()
        community_response = client.post(
            "/account/communities",
            json.dumps({"name": "test"}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 422)

    def test_create_community_with_no_body(self):
        """Test that creation of a community with no body fails"""
        client = Client()
        community_response = client.post(
            "/account/communities",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 422)

    def test_create_max_communities(self):
        """Test that a user is only allowed to create maximum 5 communities"""
        client = Client()

        # Create 5 communities
        for i in range(5):
            community_response = client.post(
                "/account/communities",
                json.dumps({"name": f"test {i}", "description": "test"}),
                content_type="application/json",
                **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
            )
            self.assertEqual(community_response.status_code, 200)

        # check that we are throwing a 401 if they have already created an account
        community_response = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 400)

       # Check that only 5 Communities are in the DB
        all_communities = list(Community.objects.all())
        self.assertEqual(len(all_communities), 5)

    def test_get_communities(self):
        """Test that getting communities works"""
        client = Client()

        # Create Community for first account
        Community.objects.create(account=self.account, name="Community for user 1", description="test")

        # Create Community for 2nd account
        Community.objects.create(account=self.account2, name="Community for user 2", description="test")

        # Get all communities
        community_response = client.get(
            "/account/communities",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        
        self.assertEqual(community_response.status_code, 200)
        json_response = community_response.json()
        self.assertEqual(len(json_response), 1)
        self.assertEqual(json_response[0]["name"], "Community for user 1")

    def test_update_community(self):
        """Test successfully editing a community's name and description"""
        client = Client()

        # Create Community
        account_community = Community.objects.create(account=self.account, name="Community 1", description="test")

        # Edit the community
        community_response = client.put(
            f"/account/communities/{account_community.id}",
            json.dumps({"name": "New Name", "description": "New Description"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(community_response.status_code, 200)
        # Check that the community was updated
        community = list(Community.objects.all())
        self.assertEqual(len(community), 1)
        self.assertEqual(community[0].name, "New Name")
        self.assertEqual(community[0].description, "New Description")

    def test_update_community_when_max_reached(self):
        """Test that a user is only allowed to create maximum 5 communities"""
        client = Client()

        # Create 5 communities
        for i in range(5):
            community_response = client.post(
                "/account/communities",
                json.dumps({"name": f"test {i}", "description": "test"}),
                content_type="application/json",
                **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
            )
            self.assertEqual(community_response.status_code, 200)

        # check that we are throwing a 401 if they have already created an account
        community_response = client.put(
            "/account/communities/3",
            json.dumps({"name": "New Name", "description": "New Description"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(community_response.status_code, 200)
        # Check that the community was updated
        community = list(Community.objects.all())
        for i in community:
            print("**** community: ", i.id, i.name, i.description)
        self.assertEqual(len(community), 5)
        self.assertEqual(community[2].name, "New Name")
        self.assertEqual(community[2].description, "New Description")
       

    def test_delete_community(self):
        """Test successfully deleting a community"""
        client = Client()

        # Create Community for first account
        account_community = Community.objects.create(
            account=self.account, name="Community1", description="test"
        )

        Community.objects.create(account=self.account2, name="Community2", description="test")

        valid_response = client.delete(
            f"/account/communities/{account_community.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        
        self.assertEqual(valid_response.status_code, 200)
        data = valid_response.json()
        self.assertTrue("ok" in data)

        # Check that the community was deleted
        all_communities = list(Community.objects.all())
        self.assertEqual(len(all_communities), 1)
        self.assertEqual(all_communities[0].name, "Community2")

