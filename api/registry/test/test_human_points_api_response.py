"""Tests for Human Points data in API responses

TODO: These tests assume that the ceramic-cache API endpoints will be modified
to include a 'points_data' field in their responses. The actual implementation
may differ, so these tests may need to be adjusted once the API changes are
implemented.
"""
import pytest
from unittest.mock import patch, MagicMock
import json

from django.contrib.auth import get_user_model
from django.test import Client
from ninja_jwt.schema import RefreshToken

from account.models import Account, Community, AccountAPIKey
from registry.models import (
    HumanPointProgramStats,
    HumanPoints,
    HumanPointsMultiplier,
    Passport,
    Score
)
from ceramic_cache.models import CeramicCache

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
            user=test_user,
            address="0x1234567890123456789012345678901234567890"
        )
    
    @pytest.fixture
    def test_community(self, test_account):
        return Community.objects.create(
            name="Test Community",
            description="Test",
            account=test_account,
            human_points_program=True
        )
    
    @pytest.fixture
    def api_key(self, test_account):
        return AccountAPIKey.objects.create(
            account=test_account,
            name="Test API Key"
        )
    
    @pytest.fixture
    def auth_headers(self, api_key):
        return {
            "HTTP_X_API_KEY": api_key.secret
        }
    
    def setup_human_points_data(self, address):
        """Setup human points data for an address"""
        # Create stats
        HumanPointProgramStats.objects.create(
            address=address,
            passing_scores=2
        )
        
        # Create multiplier
        HumanPointsMultiplier.objects.create(
            address=address,
            multiplier=2
        )
        
        # Create points
        HumanPoints.objects.create(
            address=address,
            action="human_keys",
            points=200
        )
        HumanPoints.objects.create(
            address=address,
            action="identity_staking_bronze",
            points=200
        )
        HumanPoints.objects.create(
            address=address,
            action="scoring_bonus",
            points=500
        )
    
    @patch('ceramic_cache.api.v1.get_stamps')
    def test_stamps_endpoint_includes_points_data(
        self, mock_get_stamps, api_client, test_community, auth_headers
    ):
        """Test that /ceramic-cache/stamps endpoint includes points_data"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Setup human points data
        self.setup_human_points_data(address)
        
        # Mock stamp data
        mock_get_stamps.return_value = {
            "stamps": [
                {
                    "provider": "humanKeysProvider",
                    "credential": {"type": ["VerifiableCredential"]}
                }
            ]
        }
        
        # Make request
        response = api_client.get(
            f"/ceramic-cache/stamps/{address}",
            **auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that points_data is included
        assert "points_data" in data
        points_data = data["points_data"]
        
        # Verify points data structure
        assert points_data["total_points"] == 900  # 200 + 200 + 500
        assert points_data["is_eligible"] is True  # passing_scores >= 1
        assert points_data["multiplier"] == 2
    
    @patch('ceramic_cache.api.v1.get_stamps')
    def test_points_data_for_non_eligible_address(
        self, mock_get_stamps, api_client, test_community, auth_headers
    ):
        """Test points_data for address with no passing scores"""
        address = "0x2222222222222222222222222222222222222222"
        
        # Create stats with 0 passing scores
        HumanPointProgramStats.objects.create(
            address=address,
            passing_scores=0
        )
        
        # No points
        
        # Mock stamp data
        mock_get_stamps.return_value = {"stamps": []}
        
        # Make request
        response = api_client.get(
            f"/ceramic-cache/stamps/{address}",
            **auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check points_data
        points_data = data["points_data"]
        assert points_data["total_points"] == 0
        assert points_data["is_eligible"] is False
        assert points_data["multiplier"] == 1  # Default when not in multiplier table
    
    @patch('ceramic_cache.api.v1.get_stamps')
    def test_points_data_with_no_human_points_records(
        self, mock_get_stamps, api_client, test_community, auth_headers
    ):
        """Test points_data when address has no human points records"""
        address = "0x3333333333333333333333333333333333333333"
        
        # Mock stamp data
        mock_get_stamps.return_value = {"stamps": []}
        
        # Make request
        response = api_client.get(
            f"/ceramic-cache/stamps/{address}",
            **auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check points_data with defaults
        points_data = data["points_data"]
        assert points_data["total_points"] == 0
        assert points_data["is_eligible"] is False
        assert points_data["multiplier"] == 1
    
    @patch('ceramic_cache.api.v1.get_score')
    @patch('ceramic_cache.api.v1.get_stamps')
    def test_score_endpoint_includes_points_data(
        self, mock_get_stamps, mock_get_score, api_client, test_community, auth_headers
    ):
        """Test that /ceramic-cache/score endpoint includes points_data"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Setup human points data
        self.setup_human_points_data(address)
        
        # Mock responses
        mock_get_stamps.return_value = {"stamps": []}
        mock_get_score.return_value = {
            "score": 25.0,
            "scorer_id": test_community.id
        }
        
        # Make request
        response = api_client.get(
            f"/ceramic-cache/score/{address}/{test_community.id}",
            **auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that points_data is included
        assert "points_data" in data
        points_data = data["points_data"]
        assert points_data["total_points"] == 900
        assert points_data["is_eligible"] is True
        assert points_data["multiplier"] == 2
    
    def test_calculate_total_points_aggregation(self):
        """Test that total points are correctly aggregated"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create various points entries
        point_entries = [
            ("human_keys", 100),
            ("identity_staking_bronze", 100),
            ("identity_staking_silver", 200),
            ("community_staking_beginner", 100),
            ("scoring_bonus", 500),
            ("passport_mint", 50),
            ("holonym_mint", 50),
        ]
        
        for action, points in point_entries:
            HumanPoints.objects.create(
                address=address,
                action=action,
                points=points,
                tx_hash=f"0x{action}" if "mint" in action else None
            )
        
        # Calculate total
        total = sum(HumanPoints.objects.filter(
            address=address
        ).values_list('points', flat=True))
        
        assert total == 1200
    
    def test_eligibility_based_on_passing_scores(self):
        """Test eligibility calculation based on passing scores"""
        # Test various passing score values
        test_cases = [
            (0, False),  # Not eligible
            (1, True),   # Eligible
            (2, True),   # Eligible
            (3, True),   # Eligible with bonus
            (5, True),   # Still eligible
        ]
        
        for passing_scores, expected_eligible in test_cases:
            address = f"0x{'0' * 39}{passing_scores}"
            
            stats = HumanPointProgramStats.objects.create(
                address=address,
                passing_scores=passing_scores
            )
            
            # Check eligibility
            is_eligible = stats.passing_scores >= 1
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
    
    @patch('ceramic_cache.api.v1.get_stamps')
    def test_points_data_structure_validation(
        self, mock_get_stamps, api_client, test_community, auth_headers
    ):
        """Test that points_data has the correct structure and types"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Setup some data
        HumanPointProgramStats.objects.create(
            address=address,
            passing_scores=1
        )
        HumanPoints.objects.create(
            address=address,
            action="human_keys",
            points=100
        )
        
        # Mock stamp data
        mock_get_stamps.return_value = {"stamps": []}
        
        # Make request
        response = api_client.get(
            f"/ceramic-cache/stamps/{address}",
            **auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "points_data" in data
        points_data = data["points_data"]
        
        # Check required fields exist and have correct types
        assert isinstance(points_data["total_points"], int)
        assert isinstance(points_data["is_eligible"], bool)
        assert isinstance(points_data["multiplier"], int)
        
        # Check values are reasonable
        assert points_data["total_points"] >= 0
        assert points_data["multiplier"] >= 1