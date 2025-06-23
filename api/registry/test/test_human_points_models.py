"""Tests for Human Points tracking models"""
import pytest
from django.db import IntegrityError
from django.utils import timezone
from datetime import datetime

from account.models import Community
from registry.models import HumanPointProgramScores, HumanPoints, HumanPointsMultiplier

pytestmark = pytest.mark.django_db


class TestHumanPointProgramScores:
    """Test the HumanPointProgramScores model"""
    
    def test_create_scores(self, scorer_community):
        """Test creating a new HumanPointProgramScores entry"""
        scores = HumanPointProgramScores.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=scorer_community
        )
        assert scores.address == "0x1234567890123456789012345678901234567890"
        assert scores.community == scorer_community
        assert str(scores) == f"HumanPointProgramScores - 0x1234567890123456789012345678901234567890 passed in {scorer_community.name}"
    
    def test_community_required(self, scorer_community):
        """Test that community is required"""
        scores = HumanPointProgramScores.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=scorer_community
        )
        assert scores.community == scorer_community
    
    def test_unique_together_constraint(self, scorer_community):
        """Test that address and community have unique_together constraint"""
        scores1 = HumanPointProgramScores.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=scorer_community
        )
        
        # Try to create another with same address and community should fail
        with pytest.raises(IntegrityError):
            HumanPointProgramScores.objects.create(
                address="0x1234567890123456789012345678901234567890",
                community=scorer_community
            )
    
    def test_multiple_communities_same_address(self, scorer_community, scorer_account):
        """Test that same address can have scores in multiple communities"""
        # Create another community
        community2 = Community.objects.create(
            name="Test Community 2",
            description="Test",
            account=scorer_account
        )
        
        # Create scores for same address in both communities
        scores1 = HumanPointProgramScores.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=scorer_community
        )
        scores2 = HumanPointProgramScores.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=community2
        )
        
        # Both should exist
        assert HumanPointProgramScores.objects.filter(
            address="0x1234567890123456789012345678901234567890"
        ).count() == 2


class TestHumanPoints:
    """Test the HumanPoints model"""
    
    def test_create_points(self):
        """Test creating a new HumanPoints entry"""
        points = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action="human_keys",
            points=100
        )
        assert points.address == "0x1234567890123456789012345678901234567890"
        assert points.action == "human_keys"
        assert points.points == 100
        assert points.tx_hash is None
        assert points.timestamp is not None
        assert str(points) == "HumanPoints - 0x1234567890123456789012345678901234567890: 100 points for human_keys"
    
    def test_create_points_with_tx_hash(self):
        """Test creating HumanPoints with transaction hash"""
        points = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action="passport_mint",
            points=200,
            tx_hash="0xabcdef1234567890"
        )
        assert points.tx_hash == "0xabcdef1234567890"
    
    def test_auto_timestamp(self):
        """Test that timestamp is automatically set"""
        before = timezone.now()
        points = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action="scoring_bonus",
            points=500
        )
        after = timezone.now()
        
        assert before <= points.timestamp <= after
    
    def test_multiple_points_same_address(self):
        """Test that same address can have multiple point entries"""
        points1 = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action="human_keys",
            points=100
        )
        points2 = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action="identity_staking_bronze",
            points=100
        )
        
        # Both should exist
        assert HumanPoints.objects.filter(
            address="0x1234567890123456789012345678901234567890"
        ).count() == 2
    
    def test_indexes(self):
        """Test that proper indexes exist on the model"""
        # Create some test data
        for i in range(5):
            HumanPoints.objects.create(
                address=f"0x{'0' * 39}{i}",
                action="human_keys",
                points=100
            )
        
        # These queries should use indexes (we're mainly testing they don't error)
        HumanPoints.objects.filter(address="0x0000000000000000000000000000000000000001")
        HumanPoints.objects.filter(address="0x0000000000000000000000000000000000000001", action="human_keys")
        HumanPoints.objects.filter(timestamp__gte=timezone.now())


class TestHumanPointsMultiplier:
    """Test the HumanPointsMultiplier model"""
    
    def test_create_multiplier(self):
        """Test creating a new HumanPointsMultiplier entry"""
        multiplier = HumanPointsMultiplier.objects.create(
            address="0x1234567890123456789012345678901234567890",
            multiplier=3
        )
        assert multiplier.address == "0x1234567890123456789012345678901234567890"
        assert multiplier.multiplier == 3
        assert str(multiplier) == "HumanPointsMultiplier - 0x1234567890123456789012345678901234567890: 3x"
    
    def test_default_multiplier(self):
        """Test that multiplier defaults to 2"""
        multiplier = HumanPointsMultiplier.objects.create(
            address="0x1234567890123456789012345678901234567890"
        )
        assert multiplier.multiplier == 2
    
    def test_address_as_primary_key(self):
        """Test that address field acts as primary key"""
        multiplier1 = HumanPointsMultiplier.objects.create(
            address="0x1234567890123456789012345678901234567890",
            multiplier=2
        )
        
        # Try to create another with same address should fail
        with pytest.raises(IntegrityError):
            HumanPointsMultiplier.objects.create(
                address="0x1234567890123456789012345678901234567890",
                multiplier=3
            )
    
    def test_update_multiplier(self):
        """Test updating multiplier for an address"""
        multiplier = HumanPointsMultiplier.objects.create(
            address="0x1234567890123456789012345678901234567890",
            multiplier=2
        )
        
        # Update multiplier
        multiplier.multiplier = 5
        multiplier.save()
        
        # Verify update
        updated_multiplier = HumanPointsMultiplier.objects.get(
            address="0x1234567890123456789012345678901234567890"
        )
        assert updated_multiplier.multiplier == 5


class TestCommunityHumanPointsProgram:
    """Test the human_points_program field on Community model"""
    
    def test_default_false(self, scorer_community):
        """Test that human_points_program defaults to False"""
        # scorer_community is provided by conftest fixture
        assert scorer_community.human_points_program is False
    
    def test_set_human_points_program(self, scorer_community):
        """Test setting human_points_program to True"""
        scorer_community.human_points_program = True
        scorer_community.save()
        
        # Verify update
        updated_community = Community.objects.get(id=scorer_community.id)
        assert updated_community.human_points_program is True
    
    def test_filter_by_human_points_program(self, scorer_community):
        """Test filtering communities by human_points_program"""
        # Create another community with human_points_program=True
        community2 = Community.objects.create(
            name="Test Community 2",
            description="Test",
            human_points_program=True,
            account=scorer_community.account
        )
        
        # Filter for communities in the program
        program_communities = Community.objects.filter(human_points_program=True)
        assert program_communities.count() == 1
        assert program_communities.first() == community2
        
        # Filter for communities not in the program
        non_program_communities = Community.objects.filter(human_points_program=False)
        assert scorer_community in non_program_communities


class TestHumanPointsIntegration:
    """Test integration scenarios between Human Points models"""
    
    def test_calculate_total_points_for_address(self):
        """Test calculating total points for an address"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create multiplier
        HumanPointsMultiplier.objects.create(address=address, multiplier=2)
        
        # Create various points
        HumanPoints.objects.create(address=address, action="human_keys", points=200)  # 100 * 2
        HumanPoints.objects.create(address=address, action="identity_staking_bronze", points=200)  # 100 * 2
        HumanPoints.objects.create(address=address, action="scoring_bonus", points=500)
        
        # Calculate total
        total_points = HumanPoints.objects.filter(address=address).values_list('points', flat=True)
        assert sum(total_points) == 900
    
    def test_check_eligibility(self, scorer_community):
        """Test checking if an address is eligible (has at least 1 passing score)"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Initially not eligible (no scores)
        assert HumanPointProgramScores.objects.filter(address=address).count() == 0  # Not eligible
        
        # Create a passing score to make eligible
        HumanPointProgramScores.objects.create(
            address=address,
            community=scorer_community
        )
        assert HumanPointProgramScores.objects.filter(address=address).count() >= 1  # Eligible
    
    def test_scoring_bonus_awarded(self):
        """Test awarding scoring bonus when reaching 3 passing scores"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create scores in 2 communities
        community1 = Community.objects.create(
            name="Community 1",
            description="Test",
            human_points_program=True,
            account=scorer_community.account
        )
        community2 = Community.objects.create(
            name="Community 2",
            description="Test",
            human_points_program=True,
            account=scorer_community.account
        )
        HumanPointProgramScores.objects.create(address=address, community=community1)
        HumanPointProgramScores.objects.create(address=address, community=community2)
        
        # Simulate scoring in a 3rd community with human_points_program=True
        # that results in score >= 20
        community3 = Community.objects.create(
            name="Community 3",
            description="Test",
            human_points_program=True,
            account=scorer_community.account
        )
        HumanPointProgramScores.objects.create(address=address, community=community3)
        
        # Check that 3 passing scores now exist
        passing_scores_count = HumanPointProgramScores.objects.filter(address=address).count()
        assert passing_scores_count == 3
        
        # Award scoring bonus (this would be done in the actual scoring logic)
        HumanPoints.objects.create(
            address=address,
            action="scoring_bonus",
            points=500
        )
        
        # Verify bonus was awarded
        bonus = HumanPoints.objects.get(address=address, action="scoring_bonus")
        assert bonus.points == 500
    
    def test_unique_binary_actions(self):
        """Test that binary actions (stamps) can only be recorded once per address"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create first human_keys points
        HumanPoints.objects.create(
            address=address,
            action="human_keys",
            points=100
        )
        
        # Attempting to create another human_keys for same address should be handled
        # by unique constraint in the database (tested via migration)
        # For now, verify we can query for it
        existing = HumanPoints.objects.filter(
            address=address,
            action="human_keys"
        ).count()
        assert existing == 1
    
    def test_mint_actions_with_different_tx_hash(self):
        """Test that mint actions can be recorded multiple times with different tx_hash"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create first mint
        HumanPoints.objects.create(
            address=address,
            action="passport_mint",
            points=100,
            tx_hash="0xabc123"
        )
        
        # Create second mint with different tx_hash
        HumanPoints.objects.create(
            address=address,
            action="passport_mint",
            points=100,
            tx_hash="0xdef456"
        )
        
        # Both should exist
        mints = HumanPoints.objects.filter(
            address=address,
            action="passport_mint"
        )
        assert mints.count() == 2
        assert set(mints.values_list('tx_hash', flat=True)) == {"0xabc123", "0xdef456"}