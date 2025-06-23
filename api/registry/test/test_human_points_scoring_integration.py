"""Tests for Human Points integration with passport scoring

These tests mock the passport scoring process at appropriate levels:
- Mock avalidate_credentials to return known valid stamps
- Mock scorer.acompute_score to return specific scores
- Test the human points logic that would be added to the scoring flow
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from account.models import Community
from registry.models import (
    HumanPointProgramScores, 
    HumanPoints, 
    HumanPointsMultiplier,
    Passport,
    Score,
    Stamp
)
from registry.atasks import score_passport_passport
from ceramic_cache.models import CeramicCache

pytestmark = pytest.mark.django_db


class TestHumanPointsScoringIntegration:
    """Test Human Points integration during passport scoring"""
    
    @pytest.fixture
    def human_points_community(self, scorer_account):
        """Create a community with human_points_program enabled"""
        return Community.objects.create(
            name="Human Points Test Community",
            description="Test community for Human Points",
            human_points_program=True,
            account=scorer_account
        )
    
    @pytest.fixture
    def test_passport(self):
        """Create a test passport"""
        return Passport.objects.create(
            address="0x1234567890123456789012345678901234567890"
        )
    
    @pytest.fixture
    def valid_stamps_data(self):
        """Mock validated stamps data that would be returned by avalidate_credentials"""
        return {
            "stamps": [
                {
                    "provider": "humanKeysProvider",
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": True
                },
                {
                    "provider": "gtcStakingBronze", 
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": True
                },
                {
                    "provider": "BeginnerCommunityStaker",
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": True
                },
                {
                    "provider": "someOtherProvider",  # Provider that doesn't award points
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": True
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_award_points_for_stamps(self, test_passport, valid_stamps_data, human_points_community):
        """Test that points are awarded for valid stamps during scoring"""
        # Create a multiplier for the address
        HumanPointsMultiplier.objects.create(
            address=test_passport.address,
            multiplier=2
        )
        
        # Mock the async scoring components
        with patch('registry.atasks.avalidate_credentials') as mock_validate, \
             patch('registry.atasks.acalculate_score') as mock_calculate_score:
            
            # Mock validation to return our valid stamps
            mock_validate.return_value = valid_stamps_data
            
            # Mock score calculation to return score >= 20
            mock_calculate_score.return_value = 25.0
            
            # Run scoring (assuming the human points logic is added to ascore_passport)
            await score_passport_passport(
                test_passport.address,
                human_points_community.id
            )
        
        # Check that points were awarded for valid stamps that have actions
        points = HumanPoints.objects.filter(address=test_passport.address)
        
        # Should have points for human_keys and community_staking_beginner
        # Both with 2x multiplier
        expected_actions = ["human_keys", "community_staking_beginner", "identity_staking_bronze"]
        assert points.count() == len(expected_actions)
        
        for action in expected_actions:
            point_entry = points.get(action=action)
            if action == "human_keys":
                assert point_entry.points == 200  # 100 * 2
            elif action == "community_staking_beginner":
                assert point_entry.points == 200  # 100 * 2
            elif action == "identity_staking_bronze":
                assert point_entry.points == 200  # 100 * 2
    
    @pytest.mark.asyncio
    async def test_no_points_for_invalid_stamps(self, test_passport, human_points_community):
        """Test that points are NOT awarded for invalid stamps"""
        # Create stamps data with only gtcStakingSilver (which is invalid)
        invalid_stamps_data = {
            "stamps": [
                {
                    "provider": "gtcStakingSilver",
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": False  # This stamp failed validation
                }
            ]
        }
        
        # Mock the async scoring components
        with patch('registry.atasks.avalidate_credentials') as mock_validate, \
             patch('registry.atasks.acalculate_score') as mock_calculate_score:
            
            # Mock validation to return stamps that failed validation
            mock_validate.return_value = {"stamps": []}  # No valid stamps
            
            # Mock score calculation
            mock_calculate_score.return_value = 25.0
            
            # Run scoring
            await score_passport_passport(
                test_passport.address,
                human_points_community.id
            )
        
        # Check that no points were awarded for invalid stamps
        points = HumanPoints.objects.filter(
            address=test_passport.address,
            action="identity_staking_silver"
        )
        assert points.count() == 0
    
    @pytest.mark.asyncio
    async def test_scoring_bonus_on_third_passing_score(self, test_passport, human_points_community):
        """Test that scoring bonus is awarded when reaching 3 passing scores"""
        # Setup: Create 2 existing passing scores
        community2 = Community.objects.create(
            name="Community 2",
            description="Test",
            human_points_program=True,
            account=human_points_community.account
        )
        HumanPointProgramScores.objects.create(
            address=test_passport.address,
            community=human_points_community
        )
        HumanPointProgramScores.objects.create(
            address=test_passport.address,
            community=community2
        )
        
        # Mock scoring with score >= 20
        with patch('registry.atasks.avalidate_credentials') as mock_validate, \
             patch('registry.atasks.acalculate_score') as mock_calculate_score:
            
            mock_validate.return_value = {"stamps": []}
            mock_calculate_score.return_value = 22.0
            
            # Run scoring
            await score_passport_passport(
                test_passport.address,
                human_points_community.id
            )
        
        # Check that 3 passing scores now exist
        passing_scores_count = HumanPointProgramScores.objects.filter(
            address=test_passport.address
        ).count()
        assert passing_scores_count == 3
        
        # Check that scoring bonus was awarded
        bonus = HumanPoints.objects.get(
            address=test_passport.address,
            action="scoring_bonus"
        )
        assert bonus.points == 500
    
    @pytest.mark.asyncio
    async def test_no_scoring_bonus_before_third_score(self, test_passport, human_points_community):
        """Test that no bonus is awarded before reaching 3 passing scores"""
        # Setup: Create 1 existing passing score
        HumanPointProgramScores.objects.create(
            address=test_passport.address,
            community=human_points_community
        )
        
        # Mock scoring with score >= 20
        with patch('registry.atasks.avalidate_credentials') as mock_validate, \
             patch('registry.atasks.acalculate_score') as mock_calculate_score:
            
            mock_validate.return_value = {"stamps": []}
            mock_calculate_score.return_value = 21.0
            
            # Run scoring
            await score_passport_passport(
                test_passport.address,
                human_points_community.id
            )
        
        # Check that 2 passing scores now exist
        passing_scores_count = HumanPointProgramScores.objects.filter(
            address=test_passport.address
        ).count()
        assert passing_scores_count == 2
        
        # Check that NO scoring bonus was awarded
        bonus = HumanPoints.objects.filter(
            address=test_passport.address,
            action="scoring_bonus"
        )
        assert bonus.count() == 0
    
    @pytest.mark.asyncio
    async def test_no_points_for_non_human_points_community(self, test_passport, scorer_community):
        """Test that no points are awarded when community.human_points_program=False"""
        # scorer_community has human_points_program=False by default
        assert scorer_community.human_points_program is False
        
        # Mock scoring with valid stamps
        with patch('registry.atasks.avalidate_credentials') as mock_validate, \
             patch('registry.atasks.acalculate_score') as mock_calculate_score:
            
            mock_validate.return_value = {
                "stamps": [{
                    "provider": "humanKeysProvider",
                    "credential": {"type": ["VerifiableCredential"]},
                    "verified": True
                }]
            }
            mock_calculate_score.return_value = 25.0
            
            # Run scoring
            await score_passport_passport(
                test_passport.address,
                scorer_community.id
            )
        
        # Check that NO points were awarded
        points = HumanPoints.objects.filter(address=test_passport.address)
        assert points.count() == 0
        
        # Check that NO scores were created
        scores = HumanPointProgramScores.objects.filter(address=test_passport.address)
        assert scores.count() == 0
    
    @pytest.mark.asyncio
    async def test_duplicate_stamp_points_not_awarded(self, test_passport, valid_stamps_data, human_points_community):
        """Test that points for the same stamp action are not duplicated"""
        # First scoring - award points
        with patch('registry.atasks.avalidate_credentials') as mock_validate, \
             patch('registry.atasks.acalculate_score') as mock_calculate_score:
            
            mock_validate.return_value = valid_stamps_data
            mock_calculate_score.return_value = 22.0
            
            await score_passport_passport(
                test_passport.address,
                human_points_community.id
            )
        
        initial_points_count = HumanPoints.objects.filter(
            address=test_passport.address
        ).count()
        
        # Second scoring - should not duplicate points
        with patch('registry.atasks.avalidate_credentials') as mock_validate, \
             patch('registry.atasks.acalculate_score') as mock_calculate_score:
            
            mock_validate.return_value = valid_stamps_data
            mock_calculate_score.return_value = 23.0
            
            await score_passport_passport(
                test_passport.address,
                human_points_community.id
            )
        
        # Points count should remain the same
        final_points_count = HumanPoints.objects.filter(
            address=test_passport.address
        ).count()
        assert final_points_count == initial_points_count
    
    @pytest.mark.asyncio
    async def test_points_calculation_with_different_multipliers(self, human_points_community):
        """Test points calculation with different multiplier values"""
        addresses = [
            ("0x1111111111111111111111111111111111111111", 1),
            ("0x2222222222222222222222222222222222222222", 2),
            ("0x3333333333333333333333333333333333333333", 3),
        ]
        
        for address, multiplier_value in addresses:
            # Create passport and multiplier
            passport = Passport.objects.create(address=address)
            HumanPointsMultiplier.objects.create(
                address=address,
                multiplier=multiplier_value
            )
            
            # Mock scoring
            with patch('registry.atasks.avalidate_credentials') as mock_validate, \
                 patch('registry.atasks.acalculate_score') as mock_calculate_score:
                
                mock_validate.return_value = {
                    "stamps": [{
                        "provider": "humanKeysProvider",
                        "credential": {"type": ["VerifiableCredential"]},
                        "verified": True
                    }]
                }
                mock_calculate_score.return_value = 20.0
                
                await score_passport_passport(address, human_points_community.id)
            
            # Check points
            points = HumanPoints.objects.get(
                address=address,
                action="human_keys"
            )
            assert points.points == 100 * multiplier_value
    
    @pytest.mark.asyncio
    async def test_all_stamp_types_award_correct_points(self, test_passport, human_points_community):
        """Test that all stamp types award the correct base points"""
        # Define all stamp types and their expected points
        stamp_configs = [
            ("humanKeysProvider", "human_keys", 100),
            ("gtcStakingBronze", "identity_staking_bronze", 100),
            ("gtcStakingSilver", "identity_staking_silver", 200),
            ("gtcStakingGold", "identity_staking_gold", 500),
            ("BeginnerCommunityStaker", "community_staking_beginner", 100),
            ("ExperiencedCommunityStaker", "community_staking_experienced", 200),
            ("TrustedCitizen", "community_staking_trusted", 500),
        ]
        
        # Create stamps data for all providers
        all_stamps_data = {
            "stamps": [
                {
                    "provider": provider,
                    "credential": {"type": ["VerifiableCredential"]},
                    "verified": True
                }
                for provider, _, _ in stamp_configs
            ]
        }
        
        # No multiplier (defaults to 1x in implementation)
        # Mock scoring
        with patch('registry.atasks.avalidate_credentials') as mock_validate, \
             patch('registry.atasks.acalculate_score') as mock_calculate_score:
            
            mock_validate.return_value = all_stamps_data
            mock_calculate_score.return_value = 30.0
            
            await score_passport_passport(
                test_passport.address,
                human_points_community.id
            )
        
        # Verify all points were awarded correctly
        for provider, action, base_points in stamp_configs:
            points = HumanPoints.objects.get(
                address=test_passport.address,
                action=action
            )
            # Without multiplier, points should equal base points
            assert points.points == base_points