"""Tests for Human Points API Response Integration

These tests verify that the API endpoints correctly include
points_data in their responses when human_points_program is enabled.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from ninja_jwt.schema import RefreshToken

from account.models import Account, AccountAPIKey, Community
from ceramic_cache.models import CeramicCache
from registry.models import (
    HumanPoints,
    HumanPointsCommunityQualifiedUsers,
    HumanPointsConfig,
    HumanPointsMultiplier,
    Passport,
    Score,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestHumanPointsAPIResponse:
    """Test Human Points data in API responses"""

    @pytest.fixture
    def api_client(self):
        return Client()

    @pytest.fixture
    def test_user(self):
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def test_account(self, test_user):
        return Account.objects.create(user=test_user)

    @pytest.fixture
    def human_points_community(self, test_account):
        return Community.objects.create(
            name="Test Community",
            description="Test",
            human_points_program=True,
            account=test_account,
        )

    @pytest.fixture
    def scorer_community(self, test_account):
        return Community.objects.create(
            name="Scorer Community",
            description="Test Scorer",
            human_points_program=False,
            account=test_account,
        )

    @pytest.fixture
    def api_key(self, test_account):
        return AccountAPIKey.objects.create(account=test_account, name="Test API Key")

    @pytest.fixture
    def auth_headers(self):
        # Create JWT token for ceramic-cache endpoints
        from ceramic_cache.api.v1 import DbCacheToken

        token = DbCacheToken()
        token["did"] = "did:pkh:eip155:1:0x1234567890123456789012345678901234567890"
        return {"HTTP_AUTHORIZATION": f"Bearer {str(token.access_token)}"}

    def setup_human_points_data(self, address, test_community, test_account):
        """Setup human points data for an address"""
        # First create config entries
        HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
        )
        HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.IDENTITY_STAKING_BRONZE, defaults={"points": 100}
        )
        HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.SCORING_BONUS, defaults={"points": 500}
        )

        # Create a multiplier for the address
        HumanPointsMultiplier.objects.create(address=address, multiplier=2)

        # Create passing score record (makes user eligible)
        HumanPointsCommunityQualifiedUsers.objects.create(
            address=address, community=test_community
        )

        # Create actions (normalized design - no points field)
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        )
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.IDENTITY_STAKING_BRONZE
        )
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.SCORING_BONUS
        )

    def test_ceramic_cache_score_endpoint_includes_points_data(
        self, api_client, human_points_community, auth_headers
    ):
        """Test that /ceramic-cache/score/{address} endpoint includes points_data"""
        address = "0x1234567890123456789012345678901234567890"

        # Set the community ID to match ceramic cache scorer ID
        with patch.object(
            settings, "CERAMIC_CACHE_SCORER_ID", human_points_community.id
        ):
            # Setup human points data
            self.setup_human_points_data(
                address, human_points_community, human_points_community.account
            )

            # Create a passport and score for this address
            passport = Passport.objects.create(
                address=address.lower(), community=human_points_community
            )
            Score.objects.create(
                passport=passport,
                score=Decimal("25.0"),
                status=Score.Status.DONE,
                evidence={"rawScore": "25.0", "threshold": "20.0"},
                stamps={},
            )

            # Make request
            response = api_client.get(f"/ceramic-cache/score/{address}", **auth_headers)

            assert response.status_code == 200
            data = response.json()

            # Check that points_data is included
            assert "points_data" in data
            points_data = data["points_data"]

            # Verify points data structure
            assert points_data["total_points"] == 1400  # (100 + 100) * 2 + 500 * 2
            assert points_data["is_eligible"] is True  # passing_scores >= 1
            assert points_data["multiplier"] == 2

            # Check breakdown structure
            assert "breakdown" in points_data
            breakdown = points_data["breakdown"]
            assert breakdown[HumanPoints.Action.HUMAN_KEYS] == 200  # 100 * 2
            assert (
                breakdown[HumanPoints.Action.IDENTITY_STAKING_BRONZE] == 200
            )  # 100 * 2
            assert breakdown[HumanPoints.Action.SCORING_BONUS] == 1000  # 500 * 2

    def test_points_data_for_non_eligible_address(
        self, api_client, human_points_community, auth_headers
    ):
        """Test points_data when address has no passing scores"""
        address = "0x2222222222222222222222222222222222222222"

        with patch.object(
            settings, "CERAMIC_CACHE_SCORER_ID", human_points_community.id
        ):
            # Create points but no passing scores
            HumanPointsConfig.objects.get_or_create(
                action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
            )
            HumanPoints.objects.create(
                address=address, action=HumanPoints.Action.HUMAN_KEYS
            )
            # Note: No HumanPointsCommunityQualifiedUsers entries - so is_eligible should be False

            # Create a passport and score
            passport = Passport.objects.create(
                address=address.lower(), community=human_points_community
            )
            Score.objects.create(
                passport=passport,
                score=Decimal("25.0"),
                status=Score.Status.DONE,
                evidence={"rawScore": "25.0", "threshold": "20.0"},
                stamps={},
            )

            response = api_client.get(f"/ceramic-cache/score/{address}", **auth_headers)
            data = response.json()

            assert data["points_data"]["is_eligible"] is False
            assert data["points_data"]["total_points"] == 100  # Default multiplier is 1

    def test_points_data_with_no_human_points_records(
        self, api_client, human_points_community, auth_headers
    ):
        """Test points_data when address has no human points records"""
        address = "0x3333333333333333333333333333333333333333"

        with patch.object(
            settings, "CERAMIC_CACHE_SCORER_ID", human_points_community.id
        ):
            # Create a passport and score
            passport = Passport.objects.create(
                address=address.lower(), community=human_points_community
            )
            Score.objects.create(
                passport=passport,
                score=Decimal("25.0"),
                status=Score.Status.DONE,
                evidence={"rawScore": "25.0", "threshold": "20.0"},
                stamps={},
            )

            response = api_client.get(f"/ceramic-cache/score/{address}", **auth_headers)
            data = response.json()

            # Should still include points_data with zeros
            assert "points_data" in data
            assert data["points_data"]["total_points"] == 0
            assert data["points_data"]["is_eligible"] is False
            assert data["points_data"]["multiplier"] == 1
            assert data["points_data"]["breakdown"] == {}

    def test_no_points_data_when_human_points_disabled(
        self, api_client, scorer_community, auth_headers
    ):
        """Test that points_data is None when human_points_program is disabled"""
        address = "0x5555555555555555555555555555555555555555"

        with patch.object(settings, "CERAMIC_CACHE_SCORER_ID", scorer_community.id):
            # scorer_community has human_points_program=False
            assert scorer_community.human_points_program is False

            # Create a passport and score
            passport = Passport.objects.create(
                address=address.lower(), community=scorer_community
            )
            Score.objects.create(
                passport=passport,
                score=Decimal("25.0"),
                status=Score.Status.DONE,
                evidence={"rawScore": "25.0", "threshold": "20.0"},
                stamps={},
            )

            response = api_client.get(f"/ceramic-cache/score/{address}", **auth_headers)
            data = response.json()

            # Should not include points_data or it should be None
            assert data.get("points_data") is None

    def test_calculate_total_points_aggregation(self):
        """Test that total points are correctly aggregated"""
        address = "0x1234567890123456789012345678901234567890"

        # First create config entries
        config_entries = [
            (HumanPoints.Action.HUMAN_KEYS, 100),
            (HumanPoints.Action.IDENTITY_STAKING_BRONZE, 100),
            (HumanPoints.Action.IDENTITY_STAKING_SILVER, 200),
            (HumanPoints.Action.COMMUNITY_STAKING_BEGINNER, 100),
            (HumanPoints.Action.SCORING_BONUS, 500),
            (HumanPoints.Action.PASSPORT_MINT, 300),
            (HumanPoints.Action.HUMAN_ID_MINT, 1000),
        ]
        for action, points in config_entries:
            HumanPointsConfig.objects.get_or_create(
                action=action, defaults={"points": points}
            )

        # Create various action entries
        action_entries = [
            (HumanPoints.Action.HUMAN_KEYS, None),
            (HumanPoints.Action.IDENTITY_STAKING_BRONZE, None),
            (HumanPoints.Action.IDENTITY_STAKING_SILVER, None),
            (HumanPoints.Action.COMMUNITY_STAKING_BEGINNER, None),
            (HumanPoints.Action.SCORING_BONUS, None),
            (HumanPoints.Action.PASSPORT_MINT, "0xmint1"),
            (HumanPoints.Action.HUMAN_ID_MINT, "0xmint2"),
        ]

        for action, tx_hash in action_entries:
            HumanPoints.objects.create(address=address, action=action, tx_hash=tx_hash)

        # Calculate total with normalized approach
        actions = HumanPoints.objects.filter(address=address)
        total = 0
        breakdown = {}
        for action_record in actions:
            config = HumanPointsConfig.objects.get(action=action_record.action)
            total += config.points
            breakdown[action_record.action] = config.points

        # Debug output
        expected = {
            HumanPoints.Action.HUMAN_KEYS: 100,
            HumanPoints.Action.IDENTITY_STAKING_BRONZE: 100,
            HumanPoints.Action.IDENTITY_STAKING_SILVER: 200,
            HumanPoints.Action.COMMUNITY_STAKING_BEGINNER: 100,
            HumanPoints.Action.SCORING_BONUS: 500,
            HumanPoints.Action.PASSPORT_MINT: 300,
            HumanPoints.Action.HUMAN_ID_MINT: 1000,
        }

        assert len(actions) == 7, f"Expected 7 actions, got {len(actions)}"
        assert total == 2300  # 100 + 100 + 200 + 100 + 500 + 300 + 1000 = 2300

    def test_eligibility_based_on_passing_scores(self, scorer_community):
        """Test eligibility calculation based on passing scores"""
        # Test various passing score counts
        test_cases = [
            ("0xA1111111111111111111111111111111111111111", 0, False),
            ("0xA2222222222222222222222222222222222222222", 1, True),
            ("0xA3333333333333333333333333333333333333333", 3, True),
        ]

        for address, passing_count, expected_eligible in test_cases:
            # Create passing score records
            for i in range(passing_count):
                import uuid

                comm = Community.objects.create(
                    name=f"Community {uuid.uuid4()}",
                    description="Test",
                    human_points_program=True,
                    account=scorer_community.account,
                )
                HumanPointsCommunityQualifiedUsers.objects.create(
                    address=address, community=comm
                )

            # Check eligibility
            is_eligible = HumanPointsCommunityQualifiedUsers.objects.filter(
                address=address
            ).exists()
            assert is_eligible == expected_eligible

    def test_default_multiplier_when_not_in_table(self):
        """Test that default multiplier of 1 is used when address not in multiplier table"""
        address = "0xB1111111111111111111111111111111111111111"

        # Create config and action
        HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
        )
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        )

        # Calculate points without a multiplier record
        action = HumanPoints.objects.get(address=address)
        config = HumanPointsConfig.objects.get(action=action.action)

        # When no multiplier exists, default should be 1
        try:
            multiplier = HumanPointsMultiplier.objects.get(address=address)
            mult_value = multiplier.multiplier
        except HumanPointsMultiplier.DoesNotExist:
            mult_value = 1

        total_points = config.points * mult_value
        assert total_points == 100  # 100 * 1

    def test_points_data_structure_validation(
        self, api_client, human_points_community, auth_headers
    ):
        """Test that points_data structure matches expected schema"""
        address = "0x5555555555555555555555555555555555555555"

        with patch.object(
            settings, "CERAMIC_CACHE_SCORER_ID", human_points_community.id
        ):
            # Create a passport and score
            passport = Passport.objects.create(
                address=address.lower(), community=human_points_community
            )
            Score.objects.create(
                passport=passport,
                score=Decimal("25.0"),
                status=Score.Status.DONE,
                evidence={"rawScore": "25.0", "threshold": "20.0"},
                stamps={},
            )

            response = api_client.get(f"/ceramic-cache/score/{address}", **auth_headers)
            data = response.json()

            # Validate structure
            points_data = data["points_data"]
            assert isinstance(points_data["total_points"], int)
            assert isinstance(points_data["is_eligible"], bool)
            assert isinstance(points_data["multiplier"], int)
            assert isinstance(points_data["breakdown"], dict)
