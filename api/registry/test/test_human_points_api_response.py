"""Tests for Human Points data in API responses

TODO: These tests assume that the ceramic-cache API endpoints will be modified
to include a 'points_data' field in their responses. The actual implementation
may differ, so these tests may need to be adjusted once the API changes are
implemented.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from ninja_jwt.schema import RefreshToken

from account.models import Account, AccountAPIKey, Community
from ceramic_cache.models import CeramicCache
from registry.models import (
    HumanPointProgramScores,
    HumanPoints,
    HumanPointsConfig,
    HumanPointsMultiplier,
    Passport,
    Score,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestHumanPointsAPIResponse:
    """Test Human Points data in ceramic-cache API responses"""

    @pytest.fixture
    def api_client(self):
        return Client()

    @pytest.fixture
    def test_user(self):
        return User.objects.create_user(username="testuser", password="testpass123")

    @pytest.fixture
    def test_account(self, test_user):
        return Account.objects.create(
            user=test_user, address="0x1234567890123456789012345678901234567890"
        )

    @pytest.fixture
    def test_community(self, test_account):
        return Community.objects.create(
            name="Test Community",
            description="Test",
            account=test_account,
            human_points_program=True,
        )

    @pytest.fixture
    def api_key(self, test_account):
        return AccountAPIKey.objects.create(account=test_account, name="Test API Key")

    @pytest.fixture
    def auth_headers(self, api_key):
        return {"HTTP_X_API_KEY": api_key.secret}

    def setup_human_points_data(self, address, test_community, test_account):
        """Setup human points data for an address"""
        # First create config entries
        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.HUMAN_KEYS, points=100
        )
        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.IDENTITY_STAKING_BRONZE, points=100
        )
        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.SCORING_BONUS, points=500
        )

        # Create scores in 2 communities
        community2 = Community.objects.create(
            name="Community 2",
            description="Test",
            human_points_program=True,
            account=test_account,
        )
        HumanPointProgramScores.objects.create(
            address=address, community=test_community
        )
        HumanPointProgramScores.objects.create(address=address, community=community2)

        # Create multiplier
        HumanPointsMultiplier.objects.create(address=address, multiplier=2)

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

    @patch("ceramic_cache.api.v1.get_stamps")
    def test_stamps_endpoint_includes_points_data(
        self, mock_get_stamps, api_client, test_community, auth_headers
    ):
        """Test that /ceramic-cache/stamps endpoint includes points_data"""
        address = "0x1234567890123456789012345678901234567890"

        # Setup human points data
        self.setup_human_points_data(address, test_community, test_community.account)

        # Mock stamp data
        mock_get_stamps.return_value = {
            "stamps": [
                {
                    "provider": "humanKeysProvider",
                    "credential": {"type": ["VerifiableCredential"]},
                }
            ]
        }

        # Make request
        response = api_client.get(f"/ceramic-cache/stamps/{address}", **auth_headers)

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
        assert breakdown["human_keys"] == 200  # 100 * 2
        assert breakdown["identity_staking_bronze"] == 200  # 100 * 2
        assert breakdown["scoring_bonus"] == 1000  # 500 * 2

    @patch("ceramic_cache.api.v1.get_stamps")
    def test_points_data_for_non_eligible_address(
        self, mock_get_stamps, api_client, test_community, auth_headers
    ):
        """Test points_data for address with no passing scores"""
        address = "0x2222222222222222222222222222222222222222"

        # No passing scores for this address (no HumanPointProgramScores entries)

        # No points

        # Mock stamp data
        mock_get_stamps.return_value = {"stamps": []}

        # Make request
        response = api_client.get(f"/ceramic-cache/stamps/{address}", **auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check points_data
        points_data = data["points_data"]
        assert points_data["total_points"] == 0
        assert points_data["is_eligible"] is False
        assert points_data["multiplier"] == 1  # Default when not in multiplier table

    @patch("ceramic_cache.api.v1.get_stamps")
    def test_points_data_with_no_human_points_records(
        self, mock_get_stamps, api_client, test_community, auth_headers
    ):
        """Test points_data when address has no human points records"""
        address = "0x3333333333333333333333333333333333333333"

        # Mock stamp data
        mock_get_stamps.return_value = {"stamps": []}

        # Make request
        response = api_client.get(f"/ceramic-cache/stamps/{address}", **auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check points_data with defaults
        points_data = data["points_data"]
        assert points_data["total_points"] == 0
        assert points_data["is_eligible"] is False
        assert points_data["multiplier"] == 1

    @patch("ceramic_cache.api.v1.get_score")
    @patch("ceramic_cache.api.v1.get_stamps")
    def test_score_endpoint_includes_points_data(
        self, mock_get_stamps, mock_get_score, api_client, test_community, auth_headers
    ):
        """Test that /ceramic-cache/score endpoint includes points_data"""
        address = "0x1234567890123456789012345678901234567890"

        # Setup human points data
        self.setup_human_points_data(address, test_community, test_community.account)

        # Mock responses
        mock_get_stamps.return_value = {"stamps": []}
        mock_get_score.return_value = {"score": 25.0, "scorer_id": test_community.id}

        # Make request
        response = api_client.get(
            f"/ceramic-cache/score/{address}/{test_community.id}", **auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Check that points_data is included
        assert "points_data" in data
        points_data = data["points_data"]
        assert points_data["total_points"] == 1400
        assert points_data["is_eligible"] is True
        assert points_data["multiplier"] == 2

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
            HumanPointsConfig.objects.create(action=action, points=points)

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
        for action_record in actions:
            config = HumanPointsConfig.objects.get(action=action_record.action)
            total += config.points

        assert total == 2400  # 100 + 100 + 200 + 100 + 500 + 300 + 1000

    def test_eligibility_based_on_passing_scores(self, scorer_community):
        """Test eligibility calculation based on passing scores"""
        # Test various passing score counts
        test_cases = [
            (0, False),  # Not eligible
            (1, True),  # Eligible
            (2, True),  # Eligible
            (3, True),  # Eligible with bonus
            (5, True),  # Still eligible
        ]

        for passing_scores_count, expected_eligible in test_cases:
            address = f"0x{'0' * 39}{passing_scores_count}"

            # Create the specified number of passing scores
            for i in range(passing_scores_count):
                community = Community.objects.create(
                    name=f"Community {i} for {address}",
                    description="Test",
                    human_points_program=True,
                    account=Community.objects.first().account,
                )
                HumanPointProgramScores.objects.create(
                    address=address, community=community
                )

            # Check eligibility
            scores_count = HumanPointProgramScores.objects.filter(
                address=address
            ).count()
            is_eligible = scores_count >= 1
            assert is_eligible == expected_eligible

    def test_default_multiplier_when_not_in_table(self):
        """Test that default multiplier of 1 is used when address not in multiplier table"""
        address = "0x9999999999999999999999999999999999999999"

        # Don't create multiplier entry
        multiplier_entry = HumanPointsMultiplier.objects.filter(address=address).first()
        assert multiplier_entry is None

        # In actual implementation, should default to 1
        multiplier = multiplier_entry.multiplier if multiplier_entry else 1
        assert multiplier == 1

    @patch("ceramic_cache.api.v1.get_stamps")
    def test_points_data_structure_validation(
        self, mock_get_stamps, api_client, test_community, auth_headers
    ):
        """Test that points_data has the correct structure and types"""
        address = "0x1234567890123456789012345678901234567890"

        # Setup config and data
        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.HUMAN_KEYS, points=100
        )

        HumanPointProgramScores.objects.create(
            address=address, community=test_community
        )
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        )

        # Mock stamp data
        mock_get_stamps.return_value = {"stamps": []}

        # Make request
        response = api_client.get(f"/ceramic-cache/stamps/{address}", **auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "points_data" in data
        points_data = data["points_data"]

        # Check required fields exist and have correct types
        assert isinstance(points_data["total_points"], int)
        assert isinstance(points_data["is_eligible"], bool)
        assert isinstance(points_data["multiplier"], int)
        assert isinstance(points_data["breakdown"], dict)

        # Check values are reasonable
        assert points_data["total_points"] >= 0
        assert points_data["multiplier"] >= 1

        # Check breakdown structure
        if points_data["breakdown"]:
            for action, points in points_data["breakdown"].items():
                assert isinstance(action, str)
                assert isinstance(points, int)
                assert points >= 0
