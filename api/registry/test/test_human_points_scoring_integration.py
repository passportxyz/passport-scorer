"""Tests for Human Points integration with passport scoring

These tests mock the passport scoring process at appropriate levels:
- Mock avalidate_credentials to return known valid stamps
- Mock scorer.acompute_score to return specific scores
- Test the human points logic that would be added to the scoring flow
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from account.models import Community
from ceramic_cache.models import CeramicCache
from registry.atasks import ascore_passport
from registry.human_points_utils import arecord_stamp_actions
from registry.models import (
    HumanPoints,
    HumanPointsCommunityQualifiedUsers,
    HumanPointsConfig,
    HumanPointsMultiplier,
    Passport,
    Score,
    Stamp,
)

pytestmark = pytest.mark.django_db(transaction=True)


def create_mock_credential(provider, did, with_v1_nullifier=False):
    """Helper to create a mock credential with proper structure"""
    credential = {
        "type": ["VerifiableCredential"],
        "proof": {},
        "credentialSubject": {
            "id": did,
            "provider": provider,
        },
    }

    # Add nullifiers array for Human Keys (v1 nullifier)
    if with_v1_nullifier:
        credential["credentialSubject"]["nullifiers"] = [
            f"v0:{provider}_nullifier",
            f"v1:{provider}_nullifier",  # This makes it a Human Keys stamp
        ]
    else:
        # Regular stamps just have a hash
        credential["credentialSubject"]["hash"] = f"v0.0.0:{provider}_hash_value"

    return credential


class TestHumanPointsScoringIntegration:
    """Test Human Points integration during passport scoring"""

    @pytest.mark.django_db(transaction=True)
    async def test_human_keys_detection(self):
        """Test that v0 and v1 nullifiers are correctly detected as Human Keys"""
        # Create config for Human Keys
        await HumanPointsConfig.objects.aget_or_create(
            action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
        )

        address = "0x1234567890123456789012345678901234567890"

        # Test stamps with different nullifier configurations
        test_stamps = [
            # Stamp with v1 nullifier - should be detected as Human Keys
            {
                "provider": "anyProvider",
                "credential": {
                    "credentialSubject": {
                        "provider": "anyProvider",
                        "nullifiers": ["v0:test", "v1:human_keys_nullifier"],
                    }
                },
            },
            # Stamp with only v0 nullifier - should be detected as Human Keys
            {
                "provider": "anotherProvider",
                "credential": {
                    "provider": "anotherProvider",
                    "credentialSubject": {"nullifiers": ["v0:only_v0"]},
                },
            },
            # Stamp with no nullifiers - should NOT be detected
            {
                "provider": "providerWithoutNullifiers",
                "credential": {"credentialSubject": {}},
            },
        ]

        # Process stamps
        await arecord_stamp_actions(address, test_stamps)

        # Check that two Human Keys actions were recorded (one for each stamp with v0/v1)
        human_keys_actions = await HumanPoints.objects.filter(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        ).acount()

        assert human_keys_actions == 2

        # Verify the correct nullifier(s) were stored
        human_keys_records = HumanPoints.objects.filter(
            address=address, action=HumanPoints.Action.HUMAN_KEYS
        )
        nullifiers = set([r.tx_hash async for r in human_keys_records])
        assert nullifiers.intersection({"v0:test", "v1:human_keys_nullifier", "v0:only_v0"})

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
    def valid_stamps_data(self, test_passport):
        """Mock validated stamps data that would be returned by avalidate_credentials"""
        did = f"did:pkh:eip155:1:{test_passport.address}"
        return {
            "stamps": [
                {
                    "provider": "someProviderWithHumanKeys",
                    "credential": create_mock_credential(
                        "someProviderWithHumanKeys", did, with_v1_nullifier=True
                    ),
                    "verified": True,
                },
                {
                    "provider": "SelfStakingBronze",
                    "credential": create_mock_credential("gtcStakingBronze", did),
                    "verified": True,
                },
                {
                    "provider": "BeginnerCommunityStaker",
                    "credential": create_mock_credential(
                        "BeginnerCommunityStaker", did
                    ),
                    "verified": True,
                },
                {
                    "provider": "someOtherProvider",  # Provider that doesn't award points
                    "credential": create_mock_credential("someOtherProvider", did),
                    "verified": True,
                },
            ]
        }

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    async def test_award_points_for_stamps(
        self, test_passport, valid_stamps_data, human_points_community
    ):
        """Test that points are awarded for valid stamps during scoring"""
        # First, set up the config table with point values
        await HumanPointsConfig.objects.aget_or_create(
            action=HumanPoints.Action.HUMAN_KEYS, defaults={"points": 100}
        )
        await HumanPointsConfig.objects.aget_or_create(
            action=HumanPoints.Action.IDENTITY_STAKING_BRONZE, defaults={"points": 100}
        )
        await HumanPointsConfig.objects.aget_or_create(
            action=HumanPoints.Action.COMMUNITY_STAKING_BEGINNER,
            defaults={"points": 100},
        )

        # Create a multiplier for the address
        await HumanPointsMultiplier.objects.acreate(
            address=test_passport.address, multiplier=2
        )

        # Create a passport in the community
        test_passport.community = human_points_community
        await test_passport.asave()

        # Create a score object
        score = await Score.objects.acreate(
            passport=test_passport, score=None, status=Score.Status.PROCESSING
        )

        # Mock the async scoring components
        with (
            patch("registry.atasks.aload_passport_data") as mock_load,
            patch("registry.atasks.avalidate_credentials") as mock_validate,
            patch("registry.atasks.aprocess_deduplication") as mock_dedup,
            patch("registry.atasks.aupdate_passport") as mock_update,
            patch("registry.atasks.acalculate_score") as mock_calculate_score,
        ):
            # Mock passport data loading
            mock_load.return_value = valid_stamps_data

            # Mock validation to return our valid stamps
            mock_validate.return_value = valid_stamps_data

            # Mock deduplication to return the stamps unchanged
            mock_dedup.return_value = (valid_stamps_data, {})

            # Mock update passport (no-op)
            mock_update.return_value = None

            # Mock score calculation to set passing score (binary scorers return 1 for pass)
            async def mock_calc(passport, community_id, score, clashing_stamps):
                score.score = Decimal("1")
                score.status = Score.Status.DONE
                await score.asave()
                return None

            mock_calculate_score.side_effect = mock_calc

            # Run scoring
            await ascore_passport(
                human_points_community, test_passport, test_passport.address, score
            )

        # Check that actions were recorded for valid stamps
        actions = await HumanPoints.objects.filter(
            address=test_passport.address
        ).acount()

        # Should have only HUMAN_KEYS action from the stamp with v1 nullifier
        # Provider-based actions are no longer recorded in the current implementation
        expected_actions = [
            HumanPoints.Action.HUMAN_KEYS,
        ]

        assert actions == len(expected_actions)

        # Verify actions were recorded (no points field in normalized design)
        for expected_action in expected_actions:
            exists = await HumanPoints.objects.filter(
                address=test_passport.address, action=expected_action
            ).aexists()
            assert exists
