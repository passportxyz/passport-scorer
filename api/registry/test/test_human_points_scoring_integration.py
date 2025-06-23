"""Tests for Human Points integration with passport scoring

These tests mock the passport scoring process at appropriate levels:
- Mock avalidate_credentials to return known valid stamps
- Mock scorer.acompute_score to return specific scores
- Test the human points logic that would be added to the scoring flow
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from account.models import Community
from ceramic_cache.models import CeramicCache
from registry.atasks import score_passport_passport
from registry.models import (
    HumanPointProgramScores,
    HumanPoints,
    HumanPointsConfig,
    HumanPointsMultiplier,
    Passport,
    Score,
    Stamp,
)

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
            account=scorer_account,
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
                    "verified": True,
                },
                {
                    "provider": "gtcStakingBronze",
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": True,
                },
                {
                    "provider": "BeginnerCommunityStaker",
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": True,
                },
                {
                    "provider": "someOtherProvider",  # Provider that doesn't award points
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": True,
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_award_points_for_stamps(
        self, test_passport, valid_stamps_data, human_points_community
    ):
        """Test that points are awarded for valid stamps during scoring"""
        # First, set up the config table with point values
        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.HUMAN_KEYS, points=100
        )
        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.IDENTITY_STAKING_BRONZE, points=100
        )
        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.COMMUNITY_STAKING_BEGINNER, points=100
        )

        # Create a multiplier for the address
        HumanPointsMultiplier.objects.create(
            address=test_passport.address, multiplier=2
        )

        # Mock the async scoring components
        with (
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            # Mock validation to return our valid stamps
            mock_validate.return_value = valid_stamps_data

            # Mock score calculation to return score >= 20
            mock_calculate_score.return_value = 25.0

            # Run scoring (assuming the human points logic is added to ascore_passport)
            await score_passport_passport(
                test_passport.address, human_points_community.id
            )

        # Check that actions were recorded for valid stamps
        actions = HumanPoints.objects.filter(address=test_passport.address)

        # Should have actions for human_keys, community_staking_beginner, and identity_staking_bronze
        expected_actions = [
            HumanPoints.Action.HUMAN_KEYS,
            HumanPoints.Action.COMMUNITY_STAKING_BEGINNER,
            HumanPoints.Action.IDENTITY_STAKING_BRONZE,
        ]
        assert actions.count() == len(expected_actions)

        # Verify actions were recorded (no points field in normalized design)
        for expected_action in expected_actions:
            assert actions.filter(action=expected_action).exists()

    @pytest.mark.asyncio
    async def test_no_points_for_invalid_stamps(
        self, test_passport, human_points_community
    ):
        """Test that points are NOT awarded for invalid stamps"""
        # Create stamps data with only gtcStakingSilver (which is invalid)
        invalid_stamps_data = {
            "stamps": [
                {
                    "provider": "gtcStakingSilver",
                    "credential": {"type": ["VerifiableCredential"], "proof": {}},
                    "verified": False,  # This stamp failed validation
                }
            ]
        }

        # Mock the async scoring components
        with (
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            # Mock validation to return stamps that failed validation
            mock_validate.return_value = {"stamps": []}  # No valid stamps

            # Mock score calculation
            mock_calculate_score.return_value = 25.0

            # Run scoring
            await score_passport_passport(
                test_passport.address, human_points_community.id
            )

        # Check that no actions were recorded for invalid stamps
        actions = HumanPoints.objects.filter(
            address=test_passport.address,
            action=HumanPoints.Action.IDENTITY_STAKING_SILVER,
        )
        assert actions.count() == 0

    @pytest.mark.asyncio
    async def test_scoring_bonus_on_third_passing_score(
        self, test_passport, human_points_community
    ):
        """Test that scoring bonus is awarded when reaching 3 passing scores"""
        # Setup: Create 2 existing passing scores
        community2 = Community.objects.create(
            name="Community 2",
            description="Test",
            human_points_program=True,
            account=human_points_community.account,
        )
        HumanPointProgramScores.objects.create(
            address=test_passport.address, community=human_points_community
        )
        HumanPointProgramScores.objects.create(
            address=test_passport.address, community=community2
        )

        # Mock scoring with score >= 20
        with (
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            mock_validate.return_value = {"stamps": []}
            mock_calculate_score.return_value = 22.0

            # Run scoring
            await score_passport_passport(
                test_passport.address, human_points_community.id
            )

        # Check that 3 passing scores now exist
        passing_scores_count = HumanPointProgramScores.objects.filter(
            address=test_passport.address
        ).count()
        assert passing_scores_count == 3

        # Check that scoring bonus action was recorded
        bonus = HumanPoints.objects.get(
            address=test_passport.address, action=HumanPoints.Action.SCORING_BONUS
        )
        assert bonus.action == HumanPoints.Action.SCORING_BONUS

    @pytest.mark.asyncio
    async def test_no_scoring_bonus_before_third_score(
        self, test_passport, human_points_community
    ):
        """Test that no bonus is awarded before reaching 3 passing scores"""
        # Setup: Create 1 existing passing score
        HumanPointProgramScores.objects.create(
            address=test_passport.address, community=human_points_community
        )

        # Mock scoring with score >= 20
        with (
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            mock_validate.return_value = {"stamps": []}
            mock_calculate_score.return_value = 21.0

            # Run scoring
            await score_passport_passport(
                test_passport.address, human_points_community.id
            )

        # Check that 2 passing scores now exist
        passing_scores_count = HumanPointProgramScores.objects.filter(
            address=test_passport.address
        ).count()
        assert passing_scores_count == 2

        # Check that NO scoring bonus action was recorded
        bonus = HumanPoints.objects.filter(
            address=test_passport.address, action=HumanPoints.Action.SCORING_BONUS
        )
        assert bonus.count() == 0

    @pytest.mark.asyncio
    async def test_no_points_for_non_human_points_community(
        self, test_passport, scorer_community
    ):
        """Test that no points are awarded when community.human_points_program=False"""
        # scorer_community has human_points_program=False by default
        assert scorer_community.human_points_program is False

        # Mock scoring with valid stamps
        with (
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            mock_validate.return_value = {
                "stamps": [
                    {
                        "provider": "humanKeysProvider",
                        "credential": {"type": ["VerifiableCredential"]},
                        "verified": True,
                    }
                ]
            }
            mock_calculate_score.return_value = 25.0

            # Run scoring
            await score_passport_passport(test_passport.address, scorer_community.id)

        # Check that NO actions were recorded
        actions = HumanPoints.objects.filter(address=test_passport.address)
        assert actions.count() == 0

        # Check that NO scores were created
        scores = HumanPointProgramScores.objects.filter(address=test_passport.address)
        assert scores.count() == 0

    @pytest.mark.asyncio
    async def test_duplicate_stamp_points_not_awarded(
        self, test_passport, valid_stamps_data, human_points_community
    ):
        """Test that points for the same stamp action are not duplicated"""
        # First scoring - award points
        with (
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            mock_validate.return_value = valid_stamps_data
            mock_calculate_score.return_value = 22.0

            await score_passport_passport(
                test_passport.address, human_points_community.id
            )

        initial_actions_count = HumanPoints.objects.filter(
            address=test_passport.address
        ).count()

        # Second scoring - should not duplicate actions due to unique constraints
        with (
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            mock_validate.return_value = valid_stamps_data
            mock_calculate_score.return_value = 23.0

            await score_passport_passport(
                test_passport.address, human_points_community.id
            )

        # Actions count should remain the same
        final_actions_count = HumanPoints.objects.filter(
            address=test_passport.address
        ).count()
        assert final_actions_count == initial_actions_count

    @pytest.mark.asyncio
    async def test_points_calculation_with_different_multipliers(
        self, human_points_community
    ):
        """Test points calculation with different multiplier values"""
        # Set up config
        HumanPointsConfig.objects.create(
            action=HumanPoints.Action.HUMAN_KEYS, points=100
        )

        addresses = [
            ("0x1111111111111111111111111111111111111111", 1),
            ("0x2222222222222222222222222222222222222222", 2),
            ("0x3333333333333333333333333333333333333333", 3),
        ]

        for address, multiplier_value in addresses:
            # Create passport and multiplier
            passport = Passport.objects.create(address=address)
            HumanPointsMultiplier.objects.create(
                address=address, multiplier=multiplier_value
            )

            # Mock scoring
            with (
                patch("registry.atasks.avalidate_credentials") as mock_validate,
                patch("registry.atasks.acalculate_score") as mock_calculate_score,
            ):
                mock_validate.return_value = {
                    "stamps": [
                        {
                            "provider": "humanKeysProvider",
                            "credential": {"type": ["VerifiableCredential"]},
                            "verified": True,
                        }
                    ]
                }
                mock_calculate_score.return_value = 20.0

                await score_passport_passport(address, human_points_community.id)

            # Check action was recorded
            action = HumanPoints.objects.get(
                address=address, action=HumanPoints.Action.HUMAN_KEYS
            )
            assert action.action == HumanPoints.Action.HUMAN_KEYS

            # In normalized design, points calculation happens at query time
            config = HumanPointsConfig.objects.get(action=HumanPoints.Action.HUMAN_KEYS)
            multiplier = HumanPointsMultiplier.objects.get(address=address)
            calculated_points = config.points * multiplier.multiplier
            assert calculated_points == 100 * multiplier_value

    @pytest.mark.asyncio
    async def test_all_stamp_types_award_correct_actions(
        self, test_passport, human_points_community
    ):
        """Test that all stamp types record the correct actions"""
        # First set up config for all action types
        configs = [
            (HumanPoints.Action.HUMAN_KEYS, 100),
            (HumanPoints.Action.IDENTITY_STAKING_BRONZE, 100),
            (HumanPoints.Action.IDENTITY_STAKING_SILVER, 200),
            (HumanPoints.Action.IDENTITY_STAKING_GOLD, 500),
            (HumanPoints.Action.COMMUNITY_STAKING_BEGINNER, 100),
            (HumanPoints.Action.COMMUNITY_STAKING_EXPERIENCED, 200),
            (HumanPoints.Action.COMMUNITY_STAKING_TRUSTED, 500),
        ]
        for action, points in configs:
            HumanPointsConfig.objects.create(action=action, points=points)

        # Define all stamp types and their expected actions
        stamp_mappings = [
            ("humanKeysProvider", HumanPoints.Action.HUMAN_KEYS),
            ("gtcStakingBronze", HumanPoints.Action.IDENTITY_STAKING_BRONZE),
            ("gtcStakingSilver", HumanPoints.Action.IDENTITY_STAKING_SILVER),
            ("gtcStakingGold", HumanPoints.Action.IDENTITY_STAKING_GOLD),
            ("BeginnerCommunityStaker", HumanPoints.Action.COMMUNITY_STAKING_BEGINNER),
            (
                "ExperiencedCommunityStaker",
                HumanPoints.Action.COMMUNITY_STAKING_EXPERIENCED,
            ),
            ("TrustedCitizen", HumanPoints.Action.COMMUNITY_STAKING_TRUSTED),
        ]

        # Create stamps data for all providers
        all_stamps_data = {
            "stamps": [
                {
                    "provider": provider,
                    "credential": {"type": ["VerifiableCredential"]},
                    "verified": True,
                }
                for provider, _ in stamp_mappings
            ]
        }

        # Mock scoring
        with (
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            mock_validate.return_value = all_stamps_data
            mock_calculate_score.return_value = 30.0

            await score_passport_passport(
                test_passport.address, human_points_community.id
            )

        # Verify all actions were recorded correctly
        for provider, expected_action in stamp_mappings:
            action = HumanPoints.objects.get(
                address=test_passport.address, action=expected_action
            )
            assert action.action == expected_action
