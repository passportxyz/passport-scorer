"""Test to verify the Human Points binary scoring fix

This test specifically verifies that human points are awarded when
score.score == Decimal("1") (passing binary score) and not awarded
when score.score == Decimal("0") (failing binary score).
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from account.models import Community
from registry.atasks import ascore_passport
from registry.models import (
    HumanPoints,
    HumanPointsCommunityQualifiedUsers,
    HumanPointsConfig,
    Passport,
    Score,
)

pytestmark = pytest.mark.django_db

# Import the required fixtures from conftest
from scorer.test.conftest import scorer_account, scorer_user  # noqa: F401

from .conftest import weight_config  # noqa: F401


class TestHumanPointsBinaryScoringFix:
    """Test the fix for Human Points binary scoring logic"""

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
    def test_passport(self, human_points_community):
        """Create a test passport"""
        return Passport.objects.create(
            address="0x1234567890123456789012345678901234567890",
            community=human_points_community,
        )

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    async def test_human_points_awarded_for_passing_binary_score(
        self, test_passport, human_points_community
    ):
        """Test that human points are awarded when score == 1 (passing)"""
        # Set up config
        await HumanPointsConfig.objects.aget_or_create(
            action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
        )

        # Create a score object
        score = await Score.objects.acreate(
            passport=test_passport, score=None, status=Score.Status.PROCESSING
        )

        # Mock stamps data with Human Keys
        stamps_data = {
            "stamps": [
                {
                    "provider": "humanKeys",
                    "credential": {
                        "credentialSubject": {
                            "provider": "humanKeys",
                            "nullifiers": ["v0:test", "v1:human_keys_nullifier"],
                        }
                    },
                }
            ]
        }

        # Mock the async scoring components
        with (
            patch("registry.atasks.aload_passport_data") as mock_load,
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.aprocess_deduplication") as mock_dedup,
            patch("registry.atasks.aupdate_passport") as mock_update,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            # Set up mocks
            mock_load.return_value = stamps_data
            mock_validate.return_value = stamps_data
            mock_dedup.return_value = (stamps_data, {})
            mock_update.return_value = None

            # Mock score calculation to set PASSING score (1)
            async def mock_calc(passport, community_id, score, clashing_stamps):
                score.score = Decimal("1")  # Binary passing score
                score.status = Score.Status.DONE
                await score.asave()
                return None

            mock_calculate_score.side_effect = mock_calc

            # Run scoring
            await ascore_passport(
                human_points_community, test_passport, test_passport.address, score
            )

        # Verify that human points were awarded
        qualified_users = await HumanPointsCommunityQualifiedUsers.objects.filter(
            address=test_passport.address, community=human_points_community
        ).acount()
        assert qualified_users == 1, "User should be recorded as qualified"

        # Verify Human Keys action was recorded
        human_keys_actions = await HumanPoints.objects.filter(
            address=test_passport.address, action=HumanPoints.Action.HUMAN_KEYS
        ).acount()
        assert human_keys_actions == 1, "Human Keys action should be recorded"

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    async def test_no_human_points_for_failing_binary_score(
        self, test_passport, human_points_community
    ):
        """Test that NO human points are awarded when score == 0 (failing)"""
        # Set up config
        await HumanPointsConfig.objects.aget_or_create(
            action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
        )

        # Create a score object
        score = await Score.objects.acreate(
            passport=test_passport, score=None, status=Score.Status.PROCESSING
        )

        # Mock stamps data with Human Keys
        stamps_data = {
            "stamps": [
                {
                    "provider": "humanKeys",
                    "credential": {
                        "credentialSubject": {
                            "nullifiers": ["v0:test", "v1:human_keys_nullifier"]
                        }
                    },
                }
            ]
        }

        # Mock the async scoring components
        with (
            patch("registry.atasks.aload_passport_data") as mock_load,
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.aprocess_deduplication") as mock_dedup,
            patch("registry.atasks.aupdate_passport") as mock_update,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            # Set up mocks
            mock_load.return_value = stamps_data
            mock_validate.return_value = stamps_data
            mock_dedup.return_value = (stamps_data, {})
            mock_update.return_value = None

            # Mock score calculation to set FAILING score (0)
            async def mock_calc(passport, community_id, score, clashing_stamps):
                score.score = Decimal("0")  # Binary failing score
                score.status = Score.Status.DONE
                await score.asave()
                return None

            mock_calculate_score.side_effect = mock_calc

            # Run scoring
            await ascore_passport(
                human_points_community, test_passport, test_passport.address, score
            )

        # Verify that NO human points were awarded
        qualified_users = await HumanPointsCommunityQualifiedUsers.objects.filter(
            address=test_passport.address, community=human_points_community
        ).acount()
        assert qualified_users == 0, "User should NOT be recorded as qualified"

        # Verify NO Human Keys action was recorded
        human_keys_actions = await HumanPoints.objects.filter(
            address=test_passport.address, action=HumanPoints.Action.HUMAN_KEYS
        ).acount()
        assert human_keys_actions == 0, "Human Keys action should NOT be recorded"

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    async def test_old_logic_would_never_trigger(
        self, test_passport, human_points_community
    ):
        """Demonstrate that the old logic (score >= 20) would never trigger with binary scores"""
        # Create a score object
        score = await Score.objects.acreate(
            passport=test_passport, score=None, status=Score.Status.PROCESSING
        )

        # Set score to 1 (maximum possible for binary scorers)
        score.score = Decimal("1")
        await score.asave()

        # Old logic check
        old_logic_would_trigger = score.score >= Decimal("20")
        assert not old_logic_would_trigger, (
            "Old logic (>= 20) would never trigger with binary scores"
        )

        # New logic check
        new_logic_would_trigger = score.score == Decimal("1")
        assert new_logic_would_trigger, (
            "New logic (== 1) correctly identifies passing scores"
        )
