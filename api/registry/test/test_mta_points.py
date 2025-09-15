"""Tests for MetaMask OG Points Feature

These tests verify that MetaMask OG points are correctly awarded to:
1. Addresses on the MetaMask OG list
2. With passing passport scores (20+)
3. Limited to first 5,000 eligible addresses
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from account.models import Account, AddressList, AddressListMember, Community
from registry.atasks import ascore_passport
from registry.models import (
    HumanPoints,
    HumanPointsConfig,
    Passport,
    Score,
)

pytestmark = pytest.mark.django_db(transaction=True)


@dataclass
class ScoreData:
    """Mock score data for testing"""

    score: Decimal
    evidence: list = None
    stamp_scores: dict = None
    expiration_date: datetime = None
    stamp_expiration_dates: dict = None

    def __post_init__(self):
        if self.stamp_scores is None:
            self.stamp_scores = {}
        if self.stamp_expiration_dates is None:
            self.stamp_expiration_dates = {}
        if self.expiration_date is None:
            self.expiration_date = datetime.now(timezone.utc) + timedelta(days=90)


class TestMetaMaskOG2PointsFeature:
    """Test MetaMask OG points awarding functionality"""

    @pytest.mark.asyncio
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    @patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", True)
    @patch("registry.atasks.avalidate_credentials")
    async def test_mta_points_awarded_to_list_members_with_passing_score(
        self, mock_avalidate_credentials
    ):
        """Test that MetaMask OG points are awarded to addresses on the MetaMask OG list with passing scores"""
        # Setup
        address = "0x1234567890123456789012345678901234567890"

        # Create user, account and community with human points enabled
        User = get_user_model()
        user = await User.objects.acreate(username="testuser")
        account = await Account.objects.acreate(address="0xTestAccount", user=user)
        community = await Community.objects.acreate(
            account=account,
            name="Test Community",
            human_points_program=True,
        )

        # Create MetaMask OG address list
        mta_list = await AddressList.objects.acreate(name="MetaMaskOG2")
        await mta_list.addresses.acreate(address=address.lower())

        # Create MetaMask OG points config
        await HumanPointsConfig.objects.acreate(
            action=HumanPoints.Action.METAMASK_OG_2, points=1000, active=True
        )

        # Mock successful validation with stamps
        mock_avalidate_credentials.return_value = {"stamps": []}

        # Mock scorer to return passing score (binary: 1 = pass, 0 = fail)
        mock_scorer = AsyncMock()
        mock_scorer.acompute_score.return_value = [ScoreData(score=Decimal("1"))]

        # Mock the community's aget_scorer method
        with patch.object(Community, "aget_scorer", return_value=mock_scorer):
            # Create passport and score objects
            passport = await Passport.objects.acreate(
                address=address.lower(), community=community
            )
            score = await Score.objects.acreate(passport=passport)

            # Execute
            await ascore_passport(community, passport, address, score)

        # Assert MetaMask OG points were awarded
        mta_points = await HumanPoints.objects.filter(
            address=address.lower(), action=HumanPoints.Action.METAMASK_OG_2
        ).acount()
        assert mta_points == 1

        # Verify the action was recorded correctly
        mta_point = await HumanPoints.objects.aget(
            address=address.lower(), action=HumanPoints.Action.METAMASK_OG_2
        )
        assert mta_point.action == HumanPoints.Action.METAMASK_OG_2

    @pytest.mark.asyncio
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    @patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", True)
    @patch("registry.atasks.avalidate_credentials")
    async def test_mta_points_not_awarded_without_passing_score(
        self, mock_avalidate_credentials
    ):
        """Test that MetaMask OG points are NOT awarded to addresses with failing scores"""
        # Setup
        address = "0x2234567890123456789012345678901234567890"

        # Create user, account and community
        User = get_user_model()
        user = await User.objects.acreate(username="testuser")
        account = await Account.objects.acreate(address="0xTestAccount", user=user)
        community = await Community.objects.acreate(
            account=account,
            name="Test Community",
            human_points_program=True,
        )

        # Create MetaMask OG address list with our address
        mta_list = await AddressList.objects.acreate(name="MetaMaskOG2")
        await mta_list.addresses.acreate(address=address.lower())

        # Create MetaMask OG points config
        await HumanPointsConfig.objects.acreate(
            action=HumanPoints.Action.METAMASK_OG_2, points=1000, active=True
        )

        # Mock validation
        mock_avalidate_credentials.return_value = {"stamps": []}

        # Mock scorer to return FAILING score (binary: 0 = fail)
        mock_scorer = AsyncMock()
        mock_scorer.acompute_score.return_value = [ScoreData(score=Decimal("0"))]

        # Mock the community's aget_scorer method
        with patch.object(Community, "aget_scorer", return_value=mock_scorer):
            # Create passport and score objects
            passport = await Passport.objects.acreate(
                address=address.lower(), community=community
            )
            score = await Score.objects.acreate(passport=passport)

            # Execute
            await ascore_passport(community, passport, address, score)

        # Assert NO MetaMask OG points were awarded
        mta_points = await HumanPoints.objects.filter(
            address=address.lower(), action=HumanPoints.Action.METAMASK_OG_2
        ).acount()
        assert mta_points == 0

    @pytest.mark.asyncio
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    @patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", True)
    @patch("registry.atasks.avalidate_credentials")
    async def test_mta_points_not_awarded_to_non_list_members(
        self, mock_avalidate_credentials
    ):
        """Test that MetaMask OG points are NOT awarded to addresses not on the MetaMask OG list"""
        # Setup
        address = "0x3334567890123456789012345678901234567890"

        # Create user, account and community
        User = get_user_model()
        user = await User.objects.acreate(username="testuser")
        account = await Account.objects.acreate(address="0xTestAccount", user=user)
        community = await Community.objects.acreate(
            account=account,
            name="Test Community",
            human_points_program=True,
        )

        # Create MetaMask OG address list WITHOUT our address
        mta_list = await AddressList.objects.acreate(name="MetaMaskOG2")
        await mta_list.addresses.acreate(address="0xDifferentAddress")

        # Create MetaMask OG points config
        await HumanPointsConfig.objects.acreate(
            action=HumanPoints.Action.METAMASK_OG_2, points=1000, active=True
        )

        # Mock validation
        mock_avalidate_credentials.return_value = {"stamps": []}

        # Mock scorer to return passing score (binary: 1 = pass, 0 = fail)
        mock_scorer = AsyncMock()
        mock_scorer.acompute_score.return_value = [ScoreData(score=Decimal("1"))]

        # Mock the community's aget_scorer method
        with patch.object(Community, "aget_scorer", return_value=mock_scorer):
            # Create passport and score objects
            passport = await Passport.objects.acreate(
                address=address.lower(), community=community
            )
            score = await Score.objects.acreate(passport=passport)

            # Execute
            await ascore_passport(community, passport, address, score)

        # Assert NO MetaMask OG points were awarded
        mta_points = await HumanPoints.objects.filter(
            address=address.lower(), action=HumanPoints.Action.METAMASK_OG_2
        ).acount()
        assert mta_points == 0

    @pytest.mark.asyncio
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    @patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", False)
    @patch("registry.atasks.avalidate_credentials")
    async def test_mta_points_not_awarded_when_feature_disabled(
        self, mock_avalidate_credentials
    ):
        """Test that MetaMask OG points are NOT awarded when feature flag is disabled"""
        # Setup
        address = "0x4444567890123456789012345678901234567890"

        # Create user, account and community
        User = get_user_model()
        user = await User.objects.acreate(username="testuser")
        account = await Account.objects.acreate(address="0xTestAccount", user=user)
        community = await Community.objects.acreate(
            account=account,
            name="Test Community",
            human_points_program=True,
        )

        # Create MetaMask OG address list
        mta_list = await AddressList.objects.acreate(name="MetaMaskOG2")
        await mta_list.addresses.acreate(address=address.lower())

        # Create MetaMask OG points config
        await HumanPointsConfig.objects.acreate(
            action=HumanPoints.Action.METAMASK_OG_2, points=1000, active=True
        )

        # Mock validation
        mock_avalidate_credentials.return_value = {"stamps": []}

        # Mock scorer to return passing score (binary: 1 = pass, 0 = fail)
        mock_scorer = AsyncMock()
        mock_scorer.acompute_score.return_value = [ScoreData(score=Decimal("1"))]

        # Mock the community's aget_scorer method
        with patch.object(Community, "aget_scorer", return_value=mock_scorer):
            # Create passport and score objects
            passport = await Passport.objects.acreate(
                address=address.lower(), community=community
            )
            score = await Score.objects.acreate(passport=passport)

            # Execute
            await ascore_passport(community, passport, address, score)

        # Assert NO MetaMask OG points were awarded (feature disabled)
        mta_points = await HumanPoints.objects.filter(
            address=address.lower(), action=HumanPoints.Action.METAMASK_OG_2
        ).acount()
        assert mta_points == 0

    @pytest.mark.asyncio
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    @patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", True)
    @patch("registry.atasks.avalidate_credentials")
    async def test_mta_points_limited_to_5000_addresses(
        self, mock_avalidate_credentials
    ):
        """Test that MetaMask OG points are limited to first 5000 addresses"""
        # Create user, account and community
        User = get_user_model()
        user = await User.objects.acreate(username="testuser")
        account = await Account.objects.acreate(address="0xTestAccount", user=user)
        community = await Community.objects.acreate(
            account=account,
            name="Test Community",
            human_points_program=True,
        )

        # Create MetaMask OG address list
        mta_list = await AddressList.objects.acreate(name="MetaMaskOG2")

        # Create MetaMask OG points config
        await HumanPointsConfig.objects.acreate(
            action=HumanPoints.Action.METAMASK_OG_2, points=1000, active=True
        )

        # Mock validation and scoring
        mock_avalidate_credentials.return_value = {"stamps": []}
        mock_scorer = AsyncMock()
        mock_scorer.acompute_score.return_value = [
            ScoreData(score=Decimal("1"))  # Binary: 1 = pass
        ]

        # Create 4999 existing MetaMask OG points (just under the limit)
        for i in range(4999):
            addr = f"0x{i:040x}"
            await HumanPoints.objects.acreate(
                address=addr, action=HumanPoints.Action.METAMASK_OG_2
            )

        # Add two more addresses to the list
        address_5000 = "0xAAAA567890123456789012345678901234567890"
        address_5001 = "0xBBBB567890123456789012345678901234567890"
        await mta_list.addresses.acreate(address=address_5000.lower())
        await mta_list.addresses.acreate(address=address_5001.lower())

        # Mock the community's aget_scorer method
        with patch.object(Community, "aget_scorer", return_value=mock_scorer):
            # Create passport and score for 5000th address
            passport_5000 = await Passport.objects.acreate(
                address=address_5000.lower(), community=community
            )
            score_5000 = await Score.objects.acreate(passport=passport_5000)

            # Score the 5000th address - should succeed
            await ascore_passport(community, passport_5000, address_5000, score_5000)

            # Assert 5000th address got points
            mta_points_5000 = await HumanPoints.objects.filter(
                address=address_5000.lower(), action=HumanPoints.Action.METAMASK_OG_2
            ).acount()
            assert mta_points_5000 == 1

            # Create passport and score for 5001st address
            passport_5001 = await Passport.objects.acreate(
                address=address_5001.lower(), community=community
            )
            score_5001 = await Score.objects.acreate(passport=passport_5001)

            # Score the 5001st address - should NOT get points (limit reached)
            await ascore_passport(community, passport_5001, address_5001, score_5001)

            # Assert 5001st address did NOT get points
            mta_points_5001 = await HumanPoints.objects.filter(
                address=address_5001.lower(), action=HumanPoints.Action.METAMASK_OG_2
            ).acount()
            assert mta_points_5001 == 0

            # Verify total count is exactly 5000
            total_mta_points = await HumanPoints.objects.filter(
                action=HumanPoints.Action.METAMASK_OG_2
            ).acount()
            assert total_mta_points == 5000

    @pytest.mark.asyncio
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    @patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", True)
    @patch("registry.atasks.avalidate_credentials")
    async def test_mta_points_case_insensitive_address_matching(
        self, mock_avalidate_credentials
    ):
        """Test that address matching is case-insensitive"""
        # Setup with mixed case address
        address_mixed = "0xABCD567890123456789012345678901234567890"
        address_lower = address_mixed.lower()

        # Create user, account and community
        User = get_user_model()
        user = await User.objects.acreate(username="testuser")
        account = await Account.objects.acreate(address="0xTestAccount", user=user)
        community = await Community.objects.acreate(
            account=account,
            name="Test Community",
            human_points_program=True,
        )

        # Create MetaMask OG address list with lowercase address
        mta_list = await AddressList.objects.acreate(name="MetaMaskOG2")
        await mta_list.addresses.acreate(address=address_lower)

        # Create MetaMask OG points config
        await HumanPointsConfig.objects.acreate(
            action=HumanPoints.Action.METAMASK_OG_2, points=1000, active=True
        )

        # Mock validation
        mock_avalidate_credentials.return_value = {"stamps": []}

        # Mock scorer to return passing score (binary: 1 = pass, 0 = fail)
        mock_scorer = AsyncMock()
        mock_scorer.acompute_score.return_value = [ScoreData(score=Decimal("1"))]

        # Mock the community's aget_scorer method
        with patch.object(Community, "aget_scorer", return_value=mock_scorer):
            # Create passport and score (with lowercase address as passport stores it)
            passport = await Passport.objects.acreate(
                address=address_lower,  # Passport stores lowercase
                community=community,
            )
            score = await Score.objects.acreate(passport=passport)

            # Execute with mixed case address
            await ascore_passport(
                community,
                passport,
                address_mixed,  # Mixed case in function call
                score,
            )

        # Assert MetaMask OG points were awarded (case-insensitive match)
        mta_points = await HumanPoints.objects.filter(
            address=address_lower, action=HumanPoints.Action.METAMASK_OG_2
        ).acount()
        assert mta_points == 1

    @pytest.mark.asyncio
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    @patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", True)
    @patch("registry.atasks.avalidate_credentials")
    async def test_mta_points_only_awarded_once_per_address(
        self, mock_avalidate_credentials
    ):
        """Test that each address can only receive MetaMask OG points once"""
        # Setup
        address = "0xDEAD567890123456789012345678901234567890"

        # Create user, account and community
        User = get_user_model()
        user = await User.objects.acreate(username="testuser")
        account = await Account.objects.acreate(address="0xTestAccount", user=user)
        community = await Community.objects.acreate(
            account=account,
            name="Test Community",
            human_points_program=True,
        )

        # Create MetaMask OG address list
        mta_list = await AddressList.objects.acreate(name="MetaMaskOG2")
        await mta_list.addresses.acreate(address=address.lower())

        # Create MetaMask OG points config
        await HumanPointsConfig.objects.acreate(
            action=HumanPoints.Action.METAMASK_OG_2, points=1000, active=True
        )

        # Mock validation
        mock_avalidate_credentials.return_value = {"stamps": []}

        # Mock scorer to return passing score (binary: 1 = pass, 0 = fail)
        mock_scorer = AsyncMock()
        mock_scorer.acompute_score.return_value = [ScoreData(score=Decimal("1"))]

        # Mock the community's aget_scorer method
        with patch.object(Community, "aget_scorer", return_value=mock_scorer):
            # Create passport and score objects
            passport = await Passport.objects.acreate(
                address=address.lower(), community=community
            )
            score = await Score.objects.acreate(passport=passport)

            # Score passport first time
            await ascore_passport(community, passport, address, score)

            # Score passport second time (with same objects)
            await ascore_passport(community, passport, address, score)

        # Assert only one MTA point entry exists
        mta_points = await HumanPoints.objects.filter(
            address=address.lower(), action=HumanPoints.Action.METAMASK_OG_2
        ).acount()
        assert mta_points == 1

    @pytest.mark.asyncio
    @patch("registry.atasks.settings.HUMAN_POINTS_ENABLED", True)
    @patch("registry.atasks.settings.HUMAN_POINTS_MTA_ENABLED", True)
    @patch("registry.atasks.avalidate_credentials")
    async def test_mta_points_handles_missing_address_list_gracefully(
        self, mock_avalidate_credentials
    ):
        """Test that missing MetaMask OG list doesn't break scoring"""
        # Setup
        address = "0xEEEE567890123456789012345678901234567890"

        # Create user, account and community
        User = get_user_model()
        user = await User.objects.acreate(username="testuser")
        account = await Account.objects.acreate(address="0xTestAccount", user=user)
        community = await Community.objects.acreate(
            account=account,
            name="Test Community",
            human_points_program=True,
        )

        # DO NOT create MetaMask OG address list

        # Create MetaMask OG points config
        await HumanPointsConfig.objects.acreate(
            action=HumanPoints.Action.METAMASK_OG_2, points=1000, active=True
        )

        # Mock validation
        mock_avalidate_credentials.return_value = {"stamps": []}

        # Mock scorer to return passing score (binary: 1 = pass, 0 = fail)
        mock_scorer = AsyncMock()
        mock_scorer.acompute_score.return_value = [ScoreData(score=Decimal("1"))]

        # Mock the community's aget_scorer method
        with patch.object(Community, "aget_scorer", return_value=mock_scorer):
            # Create passport and score objects
            passport = await Passport.objects.acreate(
                address=address.lower(), community=community
            )
            score = await Score.objects.acreate(passport=passport)

            # Execute - should not raise an error
            await ascore_passport(community, passport, address, score)

        # Assert NO MetaMask OG points were awarded
        mta_points = await HumanPoints.objects.filter(
            address=address.lower(), action=HumanPoints.Action.METAMASK_OG_2
        ).acount()
        assert mta_points == 0
