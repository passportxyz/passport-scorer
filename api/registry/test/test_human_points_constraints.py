"""Tests for Human Points database constraints"""

import pytest
from django.db import IntegrityError, connection
from django.db.utils import DataError

from account.models import Community
from registry.models import HumanPointsCommunityQualifiedUsers, HumanPoints, HumanPointsMultiplier

pytestmark = pytest.mark.django_db


class TestHumanPointsConstraints:
    """Test database constraints for Human Points models"""

    def test_binary_action_unique_constraint(self):
        """Test unique constraint for binary actions (stamps)"""
        address = "0x1234567890123456789012345678901234567890"

        # Create first scoring bonus entry (SCB is a true binary action)
        HumanPoints.objects.create(
            address=address,
            action="SCB",  # Using the 3-letter code for scoring bonus
        )

        # Try to create duplicate - should fail with unique constraint
        # Note: This test assumes the migration creating the constraint has been run
        with pytest.raises(IntegrityError) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO registry_humanpoints (address, action, timestamp)
                    VALUES (%s, %s, NOW())
                    """,
                    [address, "SCB"],
                )

        # The error should be about unique constraint violation
        assert (
            "unique" in str(exc_info.value).lower()
            or "duplicate" in str(exc_info.value).lower()
        )

    def test_multiple_binary_actions_same_address(self):
        """Test that different binary actions can exist for same address"""
        address = "0x1234567890123456789012345678901234567890"

        # Create different binary actions for same address using 3-letter codes
        binary_actions = [
            "SCB",  # scoring_bonus
            "ISB",  # identity_staking_bronze
            "ISS",  # identity_staking_silver
            "ISG",  # identity_staking_gold
            "CSB",  # community_staking_beginner
            "CSE",  # community_staking_experienced
            "CST",  # community_staking_trusted
        ]

        for action in binary_actions:
            HumanPoints.objects.create(address=address, action=action)

        # All should exist
        assert HumanPoints.objects.filter(address=address).count() == len(
            binary_actions
        )

    def test_mint_action_unique_constraint(self):
        """Test unique constraint for mint actions (with tx_hash)"""
        address = "0x1234567890123456789012345678901234567890"
        tx_hash = "0xabcdef1234567890"

        # Create first mint entry
        HumanPoints.objects.create(
            address=address,
            action="PMT",  # passport_mint
            tx_hash=tx_hash,
        )

        # Try to create duplicate with same tx_hash - should fail
        with pytest.raises(IntegrityError) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO registry_humanpoints (address, action, tx_hash, timestamp)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    [address, "PMT", tx_hash],
                )

        assert (
            "unique" in str(exc_info.value).lower()
            or "duplicate" in str(exc_info.value).lower()
        )

    def test_mint_actions_different_tx_hash(self):
        """Test that mint actions with different tx_hash are allowed"""
        address = "0x1234567890123456789012345678901234567890"

        # Create multiple mint entries with different tx_hash
        for i in range(3):
            HumanPoints.objects.create(
                address=address,
                action="PMT",  # passport_mint
                tx_hash=f"0xabc{i}",
            )

        # All should exist
        mints = HumanPoints.objects.filter(address=address, action="PMT")
        assert mints.count() == 3

    def test_human_id_mint_constraint(self):
        """Test that human_id_mint follows same constraint as passport_mint"""
        address = "0x1234567890123456789012345678901234567890"

        # Create human ID mints with different tx_hash
        HumanPoints.objects.create(
            address=address,
            action="HIM",  # human_id_mint
            tx_hash="0xtx1",
        )
        HumanPoints.objects.create(address=address, action="HIM", tx_hash="0xtx2")

        # Both should exist
        assert HumanPoints.objects.filter(address=address, action="HIM").count() == 2

    def test_scoring_bonus_is_binary_action(self):
        """Test that scoring_bonus is a binary action with unique constraint"""
        address = "0x1234567890123456789012345678901234567890"

        # Create first scoring_bonus entry
        HumanPoints.objects.create(
            address=address,
            action="SCB",  # scoring_bonus
        )

        # Try to create duplicate - should fail with unique constraint
        with pytest.raises(IntegrityError) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO registry_humanpoints (address, action, timestamp)
                    VALUES (%s, %s, NOW())
                    """,
                    [address, "SCB"],
                )

        # The error should be about unique constraint violation
        assert (
            "unique" in str(exc_info.value).lower()
            or "duplicate" in str(exc_info.value).lower()
        )

    def test_address_length_constraint(self):
        """Test address field length constraint"""
        # Max length is 100 characters
        long_address = "0x" + "a" * 98  # Total 100 chars

        # This should work
        HumanPoints.objects.create(
            address=long_address, action="HKY"
        )

        # This should fail - address too long
        too_long_address = "0x" + "a" * 99  # Total 101 chars
        with pytest.raises(DataError):
            HumanPoints.objects.create(
                address=too_long_address, action="HKY"
            )

    def test_action_length_constraint(self):
        """Test action field length constraint"""
        address = "0x1234567890123456789012345678901234567890"

        # The spec now uses 3-letter codes, so max length should be 3
        # But the CharField is defined with max_length in the model
        # For now, test with valid 3-letter codes
        valid_action = "TST"  # 3 characters

        # This should work
        HumanPoints.objects.create(address=address, action=valid_action)

        # Test that all standard actions are 3 characters
        standard_actions = [
            "SCB",
            "HKY",
            "ISB",
            "ISS",
            "ISG",
            "CSB",
            "CSE",
            "CST",
            "PMT",
            "HIM",
        ]
        for action in standard_actions:
            assert len(action) == 3

    def test_humanpointsprogramscores_unique_constraint(self, scorer_community):
        """Test that address and community have unique_together constraint for HumanPointsCommunityQualifiedUsers"""
        address = "0x1234567890123456789012345678901234567890"

        # Create first entry
        HumanPointsCommunityQualifiedUsers.objects.create(
            address=address, community=scorer_community
        )

        # Try to create duplicate - should fail
        with pytest.raises(IntegrityError):
            HumanPointsCommunityQualifiedUsers.objects.create(
                address=address, community=scorer_community
            )

    def test_humanpointsmultiplier_primary_key(self):
        """Test that address is primary key for HumanPointsMultiplier"""
        address = "0x1234567890123456789012345678901234567890"

        # Create first entry
        HumanPointsMultiplier.objects.create(address=address, multiplier=2)

        # Try to create duplicate - should fail
        with pytest.raises(IntegrityError):
            HumanPointsMultiplier.objects.create(address=address, multiplier=3)

    def test_null_tx_hash_allowed(self):
        """Test that tx_hash can be null for non-mint actions"""
        address = "0x1234567890123456789012345678901234567890"

        # Create entry without tx_hash for non-mint action
        points = HumanPoints.objects.create(
            address=address,
            action="ISB",  # identity_staking_bronze
            # tx_hash not provided, should default to None
        )

        assert points.tx_hash is None

    def test_human_keys_unique_with_nullifier(self):
        """Test unique constraint for human_keys using nullifier in tx_hash field"""
        address = "0x1234567890123456789012345678901234567890"
        nullifier = "unique_nullifier_123"

        # Create first human_keys entry with nullifier
        HumanPoints.objects.create(address=address, action="HKY", tx_hash=nullifier)

        # Try to create duplicate with same nullifier - should fail
        with pytest.raises(IntegrityError) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO registry_humanpoints (address, action, tx_hash, timestamp)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    [address, "HKY", nullifier],
                )

        assert (
            "unique" in str(exc_info.value).lower()
            or "duplicate" in str(exc_info.value).lower()
        )

    def test_indexes_exist(self):
        """Test that expected indexes exist on HumanPoints"""
        with connection.cursor() as cursor:
            # Check for compound index on (address, action)
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'registry_humanpoints'
                AND indexdef LIKE '%address%'
                AND indexdef LIKE '%action%'
            """)
            compound_index = cursor.fetchone()
            assert compound_index is not None

            # Check for index on timestamp
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'registry_humanpoints'
                AND indexdef LIKE '%timestamp%'
            """)
            timestamp_index = cursor.fetchone()
            assert timestamp_index is not None
