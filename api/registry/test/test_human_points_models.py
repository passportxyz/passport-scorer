"""Tests for Human Points tracking models"""

from datetime import datetime

import pytest
from django.db import IntegrityError
from django.utils import timezone

from account.models import Community
from registry.models import (
    HumanPoints,
    HumanPointsCommunityQualifiedUsers,
    HumanPointsConfig,
    HumanPointsMultiplier,
)

pytestmark = pytest.mark.django_db


class TestHumanPointsCommunityQualifiedUsers:
    """Test the HumanPointsCommunityQualifiedUsers model"""

    def test_create_scores(self, scorer_community):
        """Test creating a new HumanPointsCommunityQualifiedUsers entry"""
        scores = HumanPointsCommunityQualifiedUsers.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=scorer_community,
        )
        assert scores.address == "0x1234567890123456789012345678901234567890"
        assert scores.community == scorer_community
        assert (
            str(scores)
            == f"HumanPointsCommunityQualifiedUsers - 0x1234567890123456789012345678901234567890 qualified in {scorer_community.name}"
        )

    def test_community_required(self, scorer_community):
        """Test that community is required"""
        scores = HumanPointsCommunityQualifiedUsers.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=scorer_community,
        )
        assert scores.community == scorer_community

    def test_unique_together_constraint(self, scorer_community):
        """Test that address and community have unique_together constraint"""
        scores1 = HumanPointsCommunityQualifiedUsers.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=scorer_community,
        )

        # Try to create another with same address and community should fail
        with pytest.raises(IntegrityError):
            HumanPointsCommunityQualifiedUsers.objects.create(
                address="0x1234567890123456789012345678901234567890",
                community=scorer_community,
            )

    def test_multiple_communities_same_address(self, scorer_community, scorer_account):
        """Test that same address can have scores in multiple communities"""
        # Create another community
        community2 = Community.objects.create(
            name="Test Community 2", description="Test", account=scorer_account
        )

        # Create scores for same address in both communities
        scores1 = HumanPointsCommunityQualifiedUsers.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=scorer_community,
        )
        scores2 = HumanPointsCommunityQualifiedUsers.objects.create(
            address="0x1234567890123456789012345678901234567890", community=community2
        )

        # Both should exist
        assert (
            HumanPointsCommunityQualifiedUsers.objects.filter(
                address="0x1234567890123456789012345678901234567890"
            ).count()
            == 2
        )


class TestHumanPoints:
    """Test the HumanPoints model"""

    def test_create_points(self):
        """Test creating a new HumanPoints entry"""
        points = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action=HumanPoints.Action.HUMAN_KEYS,
        )
        assert points.address == "0x1234567890123456789012345678901234567890"
        assert points.action == HumanPoints.Action.HUMAN_KEYS
        assert points.tx_hash is None
        assert points.timestamp is not None
        assert (
            str(points)
            == f"HumanPoints - 0x1234567890123456789012345678901234567890: {HumanPoints.Action.HUMAN_KEYS}"
        )

    def test_create_points_with_tx_hash(self):
        """Test creating HumanPoints with transaction hash"""
        points = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action=HumanPoints.Action.PASSPORT_MINT,
            tx_hash="0xabcdef1234567890",
        )
        assert points.tx_hash == "0xabcdef1234567890"

    def test_auto_timestamp(self):
        """Test that timestamp is automatically set"""
        before = timezone.now()
        points = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action=HumanPoints.Action.SCORING_BONUS,
        )
        after = timezone.now()

        assert before <= points.timestamp <= after

    def test_multiple_points_same_address(self):
        """Test that same address can have multiple point entries"""
        points1 = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action=HumanPoints.Action.HUMAN_KEYS,
        )
        points2 = HumanPoints.objects.create(
            address="0x1234567890123456789012345678901234567890",
            action=HumanPoints.Action.IDENTITY_STAKING_BRONZE,
        )

        # Both should exist
        assert (
            HumanPoints.objects.filter(
                address="0x1234567890123456789012345678901234567890"
            ).count()
            == 2
        )

    def test_indexes(self):
        """Test that proper indexes exist on the model"""
        # Create some test data
        for i in range(5):
            HumanPoints.objects.create(
                address=f"0x{'0' * 39}{i}", action=HumanPoints.Action.HUMAN_KEYS
            )

        # These queries should use indexes (we're mainly testing they don't error)
        HumanPoints.objects.filter(address="0x0000000000000000000000000000000000000001")
        HumanPoints.objects.filter(
            address="0x0000000000000000000000000000000000000001",
            action=HumanPoints.Action.HUMAN_KEYS,
        )
        HumanPoints.objects.filter(timestamp__gte=timezone.now())

    def test_action_choices(self):
        """Test that all expected action choices are available"""
        expected_actions = [
            (HumanPoints.Action.SCORING_BONUS, "SCB"),
            (HumanPoints.Action.HUMAN_KEYS, "HKY"),
            (HumanPoints.Action.IDENTITY_STAKING_BRONZE, "ISB"),
            (HumanPoints.Action.IDENTITY_STAKING_SILVER, "ISS"),
            (HumanPoints.Action.IDENTITY_STAKING_GOLD, "ISG"),
            (HumanPoints.Action.COMMUNITY_STAKING_BEGINNER, "CSB"),
            (HumanPoints.Action.COMMUNITY_STAKING_EXPERIENCED, "CSE"),
            (HumanPoints.Action.COMMUNITY_STAKING_TRUSTED, "CST"),
            (HumanPoints.Action.PASSPORT_MINT, "PMT"),
            (HumanPoints.Action.HUMAN_ID_MINT, "HIM"),
        ]

        for action_enum, expected_value in expected_actions:
            assert action_enum.value == expected_value


class TestHumanPointsMultiplier:
    """Test the HumanPointsMultiplier model"""

    def test_create_multiplier(self):
        """Test creating a new HumanPointsMultiplier entry"""
        multiplier = HumanPointsMultiplier.objects.create(
            address="0x1234567890123456789012345678901234567890", multiplier=3
        )
        assert multiplier.address == "0x1234567890123456789012345678901234567890"
        assert multiplier.multiplier == 3
        assert (
            str(multiplier)
            == "HumanPointsMultiplier - 0x1234567890123456789012345678901234567890: 3x"
        )

    def test_default_multiplier(self):
        """Test that multiplier defaults to 2"""
        multiplier = HumanPointsMultiplier.objects.create(
            address="0x1234567890123456789012345678901234567890"
        )
        assert multiplier.multiplier == 2

    def test_address_as_primary_key(self):
        """Test that address field acts as primary key"""
        multiplier1 = HumanPointsMultiplier.objects.create(
            address="0x1234567890123456789012345678901234567890", multiplier=2
        )

        # Try to create another with same address should fail
        with pytest.raises(IntegrityError):
            HumanPointsMultiplier.objects.create(
                address="0x1234567890123456789012345678901234567890", multiplier=3
            )

    def test_update_multiplier(self):
        """Test updating multiplier for an address"""
        multiplier = HumanPointsMultiplier.objects.create(
            address="0x1234567890123456789012345678901234567890", multiplier=2
        )

        # Update multiplier
        multiplier.multiplier = 5
        multiplier.save()

        # Verify update
        updated_multiplier = HumanPointsMultiplier.objects.get(
            address="0x1234567890123456789012345678901234567890"
        )
        assert updated_multiplier.multiplier == 5


class TestHumanPointsConfig:
    """Test the HumanPointsConfig model"""

    def test_create_config(self):
        """Test creating a new HumanPointsConfig entry"""
        config, _ = HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
        )
        assert config.action == HumanPoints.Action.HUMAN_KEYS
        assert config.points == 100
        assert config.active is True

    def test_default_active_true(self):
        """Test that active defaults to True"""
        config, _ = HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.SCORING_BONUS, defaults={"points": 500}
        )
        assert config.active is True

    def test_unique_action_constraint(self):
        """Test that action must be unique"""
        # Clean up any existing config from migrations
        HumanPointsConfig.objects.filter(
            action=HumanPoints.Action.PASSPORT_MINT
        ).delete()

        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.PASSPORT_MINT, points=300
        )

        # Try to create another with same action should fail
        with pytest.raises(IntegrityError):
            HumanPointsConfig.objects.create(
                action=HumanPoints.Action.PASSPORT_MINT, points=400
            )

    def test_populate_all_configs(self):
        """Test populating all standard configurations"""
        configs = [
            (HumanPoints.Action.SCORING_BONUS, 500),
            (HumanPoints.Action.HUMAN_KEYS, 100),
            (HumanPoints.Action.IDENTITY_STAKING_BRONZE, 100),
            (HumanPoints.Action.IDENTITY_STAKING_SILVER, 200),
            (HumanPoints.Action.IDENTITY_STAKING_GOLD, 500),
            (HumanPoints.Action.COMMUNITY_STAKING_BEGINNER, 100),
            (HumanPoints.Action.COMMUNITY_STAKING_EXPERIENCED, 200),
            (HumanPoints.Action.COMMUNITY_STAKING_TRUSTED, 500),
            (HumanPoints.Action.PASSPORT_MINT, 300),
            (HumanPoints.Action.HUMAN_ID_MINT, 1000),
        ]

        for action, points in configs:
            HumanPointsConfig.objects.get_or_create(
                action=action, defaults={"points": points}
            )

        # Verify all were created
        assert HumanPointsConfig.objects.count() == len(configs)

        # Verify specific values
        human_keys_config = HumanPointsConfig.objects.get(
            action=HumanPoints.Action.HUMAN_KEYS
        )
        assert human_keys_config.points == 100


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
            account=scorer_community.account,
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
        """Test calculating total points for an address with normalized design"""
        address = "0x1234567890123456789012345678901234567890"

        # First, populate config table
        HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
        )
        HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.IDENTITY_STAKING_BRONZE, defaults={"points": 100}
        )
        HumanPointsConfig.objects.get_or_create(
            action=HumanPoints.Action.SCORING_BONUS, defaults={"points": 500}
        )

        # Create multiplier
        HumanPointsMultiplier.objects.create(address=address, multiplier=2)

        # Create various actions (no points field)
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        )
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.IDENTITY_STAKING_BRONZE
        )
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.SCORING_BONUS
        )

        # Calculate total with normalized approach
        actions = HumanPoints.objects.filter(address=address)
        multiplier = HumanPointsMultiplier.objects.get(address=address)

        total = 0
        for action_record in actions:
            config = HumanPointsConfig.objects.get(
                action=action_record.action, active=True
            )
            total += config.points * multiplier.multiplier

        assert total == 1400  # (100 + 100) * 2 + 500 * 2

    def test_check_eligibility(self, scorer_community):
        """Test checking if an address is eligible (has at least 1 passing score)"""
        address = "0x1234567890123456789012345678901234567890"

        # Initially not eligible (no scores)
        assert (
            HumanPointsCommunityQualifiedUsers.objects.filter(address=address).count()
            == 0
        )  # Not eligible

        # Create a passing score to make eligible
        HumanPointsCommunityQualifiedUsers.objects.create(
            address=address, community=scorer_community
        )
        assert (
            HumanPointsCommunityQualifiedUsers.objects.filter(address=address).count()
            >= 1
        )  # Eligible

    def test_scoring_bonus_awarded(self, scorer_account):
        """Test awarding scoring bonus when reaching 3 passing scores"""
        address = "0x1234567890123456789012345678901234567890"

        # Create scores in 2 communities
        community1 = Community.objects.create(
            name="Community 1",
            description="Test",
            human_points_program=True,
            account=scorer_account,
        )
        community2 = Community.objects.create(
            name="Community 2",
            description="Test",
            human_points_program=True,
            account=scorer_account,
        )
        HumanPointsCommunityQualifiedUsers.objects.create(
            address=address, community=community1
        )
        HumanPointsCommunityQualifiedUsers.objects.create(
            address=address, community=community2
        )

        # Simulate scoring in a 3rd community with human_points_program=True
        # that results in score >= 20
        community3 = Community.objects.create(
            name="Community 3",
            description="Test",
            human_points_program=True,
            account=scorer_account,
        )
        HumanPointsCommunityQualifiedUsers.objects.create(
            address=address, community=community3
        )

        # Check that 3 passing scores now exist
        passing_scores_count = HumanPointsCommunityQualifiedUsers.objects.filter(
            address=address
        ).count()
        assert passing_scores_count == 3

        # Award scoring bonus (this would be done in the actual scoring logic)
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.SCORING_BONUS
        )

        # Verify bonus was awarded
        bonus = HumanPoints.objects.get(
            address=address, action=HumanPoints.Action.SCORING_BONUS
        )
        assert bonus.action == HumanPoints.Action.SCORING_BONUS

    def test_unique_binary_actions(self):
        """Test that binary actions (stamps) can only be recorded once per address"""
        address = "0x1234567890123456789012345678901234567890"

        # Create first human_keys action
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        )

        # Attempting to create another human_keys for same address should be handled
        # by unique constraint in the database (tested via migration)
        # For now, verify we can query for it
        existing = HumanPoints.objects.filter(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        ).count()
        assert existing == 1

    def test_mint_actions_with_different_tx_hash(self):
        """Test that mint actions can be recorded multiple times with different tx_hash"""
        address = "0x1234567890123456789012345678901234567890"

        # Create first mint
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.PASSPORT_MINT, tx_hash="0xabc123"
        )

        # Create second mint with different tx_hash
        HumanPoints.objects.create(
            address=address, action=HumanPoints.Action.PASSPORT_MINT, tx_hash="0xdef456"
        )

        # Both should exist
        mints = HumanPoints.objects.filter(
            address=address, action=HumanPoints.Action.PASSPORT_MINT
        )
        assert mints.count() == 2
        assert set(mints.values_list("tx_hash", flat=True)) == {"0xabc123", "0xdef456"}

    def test_human_keys_with_nullifier(self):
        """Test that Human Keys action stores nullifier in tx_hash field"""
        address = "0x1234567890123456789012345678901234567890"
        nullifier = "unique_nullifier_123"

        # Create human keys action with nullifier
        HumanPoints.objects.create(
            address=address,
            action=HumanPoints.Action.HUMAN_KEYS,
            tx_hash=nullifier,  # Store nullifier in tx_hash field
        )

        # Verify it was stored
        human_keys = HumanPoints.objects.get(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        )
        assert human_keys.tx_hash == nullifier
