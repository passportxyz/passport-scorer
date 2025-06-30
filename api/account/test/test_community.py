import json
from datetime import datetime, timezone
from typing import cast

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.db.utils import IntegrityError
from django.test import Client, TestCase
from ninja_jwt.schema import RefreshToken

from account.models import Account, Community
from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS

# Avoids type issues in standard django models
user_manager = cast(UserManager, get_user_model().objects)

mock_community_body = {
    "name": "test",
    "description": "test",
    "use_case": "sybil protection",
    "scorer": "WEIGHTED_BINARY",
}


class CommunityTestCase(TestCase):
    def setUp(self):
        user_manager.create_user(username="admin", password="12345")

        self.user = user_manager.create_user(username="testuser-1", password="12345")
        self.user2 = user_manager.create_user(username="testuser-2", password="12345")

        # Avoids type issues in standard ninja models
        refresh = cast(RefreshToken, RefreshToken.for_user(self.user))
        refresh["ip_address"] = "127.0.0.1"
        self.access_token = refresh.access_token

        (self.account, _) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )
        (self.account2, _) = Account.objects.get_or_create(
            user=self.user2, defaults={"address": "0x0"}
        )

        config = WeightConfiguration.objects.create(
            version="v1",
            threshold=5.0,
            active=True,
            description="Test",
        )

        for provider, weight in GITCOIN_PASSPORT_WEIGHTS.items():
            WeightConfigurationItem.objects.create(
                weight_configuration=config,
                provider=provider,
                weight=float(weight),
            )

    def test_create_community(self):
        """Test that creation of a community works and that attributes are saved correctly"""
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
        c = all_communities[0]
        self.assertEqual(c.use_case, mock_community_body["use_case"])
        self.assertEqual(c.name, mock_community_body["name"])
        self.assertEqual(c.description, mock_community_body["description"])
        self.assertEqual(c.rule, "LIFO")

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
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)

        community_response1 = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response1.status_code, 400)
        response_data = community_response1.json()
        self.assertEqual(
            response_data, {"detail": "A community with this name already exists"}
        )

    def test_create_community_with_deleted_duplicate_name(self):
        """Test that creation of a community with duplicate name passes if the original community was deleted"""
        client = Client()
        # create first community
        community_response = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)

        # mark deleted
        pk = Community.objects.get(name=mock_community_body["name"]).pk
        valid_response = client.delete(
            f"/account/communities/{pk}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(valid_response.status_code, 200)

        # successfully create community with same name
        community_response1 = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response1.status_code, 200)

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
            community_body = dict(**mock_community_body)
            community_body["name"] = f"test {i}"
            community_response = client.post(
                "/account/communities",
                json.dumps(community_body),
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

    def test_deleted_do_not_count_towards_max(self):
        """Test that a user is only allowed to create maximum 5 non-deleted communities"""
        client = Client()

        # Create 5 communities
        for i in range(5):
            community_body = dict(**mock_community_body)
            community_body["name"] = f"test {i}"
            community_response = client.post(
                "/account/communities",
                json.dumps(community_body),
                content_type="application/json",
                **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
            )
            self.assertEqual(community_response.status_code, 200)

        # delete one
        last_community = Community.objects.filter(account=self.account)[4]
        last_community.deleted_at = datetime.now(timezone.utc)
        last_community.save()

        # check that we can create another community
        community_response = client.post(
            "/account/communities",
            json.dumps(mock_community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)

        # Check that 6 Communities are in the DB
        all_communities = list(Community.objects.all())
        self.assertEqual(len(all_communities), 6)

    def test_get_communities(self):
        """Test that getting communities works"""
        client = Client()

        # Create Community for first account
        Community.objects.create(
            account=self.account, name="Community for user 1", description="test"
        )

        # Create Community for 2nd account (should not be returned)
        Community.objects.create(
            account=self.account2, name="Community for user 2", description="test"
        )

        # Create Community for 1st account (should not be returned)
        Community.objects.create(
            account=self.account,
            name="Deleted Community for user 1",
            description="test",
            deleted_at=datetime.now(timezone.utc),
        )

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
        self.assertIn("threshold", json_response[0])
        self.assertIsInstance(json_response[0]["threshold"], float)

    def test_update_community(self):
        """Test successfully editing a community's name and description"""
        client = Client()

        # Create Community
        account_community = Community.objects.create(
            account=self.account,
            name="OLD - " + mock_community_body["name"],
            description="OLD - " + mock_community_body["description"],
        )

        # Edit the community
        community_response = client.put(
            f"/account/communities/{account_community.pk}",
            json.dumps(mock_community_body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(community_response.status_code, 200)
        # Check that the community was updated
        community = list(Community.objects.all())
        self.assertEqual(len(community), 1)
        self.assertEqual(community[0].name, mock_community_body["name"])
        self.assertEqual(community[0].description, mock_community_body["description"])

    def test_update_community_with_duplicate_name(self):
        """Test successfully editing a community's name and description"""
        client = Client()

        name_1 = "OLD - " + mock_community_body["name"]
        name_2 = "OLD-2 - " + mock_community_body["name"]

        # Create Community 1
        account_community = Community.objects.create(
            account=self.account,
            name=name_1,
            description="OLD - " + mock_community_body["description"],
        )

        # Create Community 2
        Community.objects.create(
            account=self.account,
            name=name_2,
            description="OLD-2 - " + mock_community_body["description"],
        )

        # Edit the community
        community_body = dict(**mock_community_body)
        community_body["name"] = name_2
        community_response = client.put(
            f"/account/communities/{account_community.pk}",
            json.dumps(community_body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(community_response.status_code, 400)
        response_data = community_response.json()
        self.assertEqual(
            response_data, {"detail": "A community with this name already exists"}
        )

    def test_update_community_when_max_reached(self):
        """Test that a user is only allowed to create maximum 5 communities"""
        client = Client()

        # Create 5 communities
        for i in range(5):
            community_body = dict(**mock_community_body)
            community_body["name"] = f"test {i}"
            community_response = client.post(
                "/account/communities",
                json.dumps(community_body),
                content_type="application/json",
                **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
            )
            self.assertEqual(community_response.status_code, 200)

        community_response = client.get(
            "/account/communities",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)
        community_id = community_response.json()[2]["id"]

        self.assertEqual(community_response.status_code, 200)
        json_response = community_response.json()

        # check that we are throwing a 401 if they have already created an account
        community_body = dict(**mock_community_body)
        community_body["name"] = "New Name"
        community_body["description"] = "New Description"
        community_response = client.put(
            f"/account/communities/{community_id}",
            json.dumps(community_body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(community_response.status_code, 200)
        # Check that the community was updated
        community = Community.objects.get(pk=community_id)
        self.assertEqual(len(list(Community.objects.all())), 5)
        self.assertEqual(community.name, "New Name")
        self.assertEqual(community.description, "New Description")

    def test_delete_community(self):
        """Test successfully deleting a community"""
        client = Client()

        # Create Community for first account
        account_community = Community.objects.create(
            account=self.account, name="Community1", description="test"
        )

        Community.objects.create(
            account=self.account2, name="Community2", description="test"
        )

        valid_response = client.delete(
            f"/account/communities/{account_community.pk}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(valid_response.status_code, 200)
        data = valid_response.json()
        self.assertTrue("ok" in data)

        # Check that the community was deleted
        all_communities = list(Community.objects.all())
        self.assertEqual(len(all_communities), 2)
        non_deleted_communities = list(Community.objects.filter(deleted_at=None))
        self.assertEqual(len(non_deleted_communities), 1)
        self.assertEqual(non_deleted_communities[0].name, "Community2")

    def test_patch_community(self):
        """Test successfully editing a community's name and description"""
        client = Client()

        # Create Community
        account_community = Community.objects.create(
            account=self.account,
            name="OLD - " + mock_community_body["name"],
            description="OLD - " + mock_community_body["description"],
        )

        # Edit the community
        community_response = client.patch(
            f"/account/communities/{account_community.pk}",
            json.dumps(
                {
                    "name": mock_community_body["name"],
                    "description": mock_community_body["description"],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(community_response.status_code, 200)
        # Check that the community was updated
        community = list(Community.objects.all())
        self.assertEqual(len(community), 1)
        self.assertEqual(community[0].name, mock_community_body["name"])
        self.assertEqual(community[0].description, mock_community_body["description"])

    def test_patch_community_with_duplicate_name(self):
        """Test successfully editing a community's name and description"""
        client = Client()

        name_1 = "OLD - " + mock_community_body["name"]
        name_2 = "OLD-2 - " + mock_community_body["name"]

        # Create Community 1
        account_community = Community.objects.create(
            account=self.account,
            name=name_1,
            description="OLD - " + mock_community_body["description"],
        )

        # Create Community 2
        Community.objects.create(
            account=self.account,
            name=name_2,
            description="OLD-2 - " + mock_community_body["description"],
        )

        # Edit the community
        community_response = client.patch(
            f"/account/communities/{account_community.pk}",
            json.dumps(
                {
                    "name": name_2,
                    "description": mock_community_body["description"],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(community_response.status_code, 400)
        response_data = community_response.json()
        self.assertEqual(
            response_data, {"detail": "A community with this name already exists"}
        )

    def test_no_duplicate_communitie(self):
        """Make sure that it is not possible to have duplicate stamps in the DB"""

        # Create the first community
        Community.objects.create(
            account=self.account,
            name="Test",
            description="some description",
        )

        with pytest.raises(IntegrityError) as exc_info:
            # Create the same community again
            # We expect an exception to be thrown
            Community.objects.create(
                account=self.account,
                name="Test",
                description="some description",
            )

    def test_patch_community_threshold(self):
        """Test updating a community's threshold via PATCH"""
        client = Client()

        # Create Community
        account_community = Community.objects.create(
            account=self.account,
            name="Threshold Community",
            description="desc",
        )
        scorer = (
            account_community.get_scorer()
            if hasattr(account_community, "get_scorer")
            else None
        )
        self.assertIsNotNone(scorer)
        # Only test threshold update if scorer has threshold attribute
        if hasattr(scorer, "threshold"):
            old_threshold = float(getattr(scorer, "threshold", 20.0))
            new_threshold = old_threshold + 5.5
            patch_body = {"threshold": new_threshold}
            response = client.patch(
                f"/account/communities/{account_community.pk}",
                json.dumps(patch_body),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )
            self.assertEqual(response.status_code, 200)
            scorer.refresh_from_db()
            self.assertEqual(float(scorer.threshold), new_threshold)
        else:
            # Should not error, but threshold is not settable
            patch_body = {"threshold": 42.0}
            response = client.patch(
                f"/account/communities/{account_community.pk}",
                json.dumps(patch_body),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )
            self.assertEqual(response.status_code, 200)

    def test_patch_community_threshold_weighted(self):
        """Test PATCHing threshold on a WeightedScorer community does not error and sets threshold"""
        client = Client()
        # Create Community with WEIGHTED scorer
        community_body = dict(**mock_community_body)
        community_body["name"] = "Weighted Scorer Community"
        community_body["scorer"] = "WEIGHTED"
        community_response = client.post(
            "/account/communities",
            json.dumps(community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)
        community = Community.objects.get(name="Weighted Scorer Community")
        scorer = community.get_scorer() if hasattr(community, "get_scorer") else None
        self.assertIsNotNone(scorer)
        self.assertTrue(hasattr(scorer, "threshold"))
        patch_body = {"threshold": 123.45}
        response = client.patch(
            f"/account/communities/{community.pk}",
            json.dumps(patch_body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(response.status_code, 200)
        scorer.refresh_from_db()
        self.assertEqual(float(scorer.threshold), 123.45)

    def test_patch_community_threshold_binary_weighted(self):
        """Test PATCHing threshold on a BinaryWeightedScorer community updates threshold"""
        client = Client()
        # Create Community with WEIGHTED_BINARY scorer
        community_body = dict(**mock_community_body)
        community_body["name"] = "Binary Scorer Community"
        community_body["scorer"] = "WEIGHTED_BINARY"
        community_response = client.post(
            "/account/communities",
            json.dumps(community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)
        community = Community.objects.get(name="Binary Scorer Community")
        scorer = community.get_scorer() if hasattr(community, "get_scorer") else None
        self.assertIsNotNone(scorer)
        self.assertTrue(hasattr(scorer, "threshold"))
        old_threshold = float(scorer.threshold)
        new_threshold = old_threshold + 7.7
        patch_body = {"threshold": new_threshold}
        response = client.patch(
            f"/account/communities/{community.pk}",
            json.dumps(patch_body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(response.status_code, 200)
        scorer.refresh_from_db()
        self.assertEqual(float(scorer.threshold), new_threshold)

    def test_create_community_with_custom_threshold(self):
        """Test that POST /communities sets the threshold on the new BinaryWeightedScorer if provided"""
        client = Client()
        custom_threshold = 42.42
        community_body = dict(**mock_community_body)
        community_body["name"] = "Custom Threshold Community"
        community_body["threshold"] = custom_threshold
        community_response = client.post(
            "/account/communities",
            json.dumps(community_body),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"},
        )
        self.assertEqual(community_response.status_code, 200)
        community = Community.objects.get(name="Custom Threshold Community")
        scorer = community.get_scorer() if hasattr(community, "get_scorer") else None
        self.assertIsNotNone(scorer)
        self.assertTrue(hasattr(scorer, "threshold"))
        self.assertEqual(float(scorer.threshold), custom_threshold)
