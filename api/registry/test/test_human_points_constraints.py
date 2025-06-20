"""Tests for Human Points database constraints"""
import pytest
from django.db import IntegrityError, connection
from django.db.utils import DataError

from registry.models import HumanPoints, HumanPointsMultiplier, HumanPointProgramStats

pytestmark = pytest.mark.django_db


class TestHumanPointsConstraints:
    """Test database constraints for Human Points models"""
    
    def test_binary_action_unique_constraint(self):
        """Test unique constraint for binary actions (stamps)"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create first human_keys entry
        HumanPoints.objects.create(
            address=address,
            action="human_keys",
            points=100
        )
        
        # Try to create duplicate - should fail with unique constraint
        # Note: This test assumes the migration creating the constraint has been run
        with pytest.raises(IntegrityError) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO registry_humanpoints (address, action, points, timestamp)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    [address, "human_keys", 200]
                )
        
        # The error should be about unique constraint violation
        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()
    
    def test_multiple_binary_actions_same_address(self):
        """Test that different binary actions can exist for same address"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create different binary actions for same address
        binary_actions = [
            "human_keys",
            "identity_staking_bronze",
            "identity_staking_silver",
            "identity_staking_gold",
            "community_staking_beginner",
            "community_staking_experienced",
            "community_staking_trusted"
        ]
        
        for action in binary_actions:
            HumanPoints.objects.create(
                address=address,
                action=action,
                points=100
            )
        
        # All should exist
        assert HumanPoints.objects.filter(address=address).count() == len(binary_actions)
    
    def test_mint_action_unique_constraint(self):
        """Test unique constraint for mint actions (with tx_hash)"""
        address = "0x1234567890123456789012345678901234567890"
        tx_hash = "0xabcdef1234567890"
        
        # Create first mint entry
        HumanPoints.objects.create(
            address=address,
            action="passport_mint",
            points=100,
            tx_hash=tx_hash
        )
        
        # Try to create duplicate with same tx_hash - should fail
        with pytest.raises(IntegrityError) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO registry_humanpoints (address, action, points, tx_hash, timestamp)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    [address, "passport_mint", 100, tx_hash]
                )
        
        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()
    
    def test_mint_actions_different_tx_hash(self):
        """Test that mint actions with different tx_hash are allowed"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create multiple mint entries with different tx_hash
        for i in range(3):
            HumanPoints.objects.create(
                address=address,
                action="passport_mint",
                points=100,
                tx_hash=f"0xabc{i}"
            )
        
        # All should exist
        mints = HumanPoints.objects.filter(
            address=address,
            action="passport_mint"
        )
        assert mints.count() == 3
    
    def test_holonym_mint_constraint(self):
        """Test that holonym_mint follows same constraint as passport_mint"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create holonym mints with different tx_hash
        HumanPoints.objects.create(
            address=address,
            action="holonym_mint",
            points=50,
            tx_hash="0xtx1"
        )
        HumanPoints.objects.create(
            address=address,
            action="holonym_mint",
            points=50,
            tx_hash="0xtx2"
        )
        
        # Both should exist
        assert HumanPoints.objects.filter(
            address=address,
            action="holonym_mint"
        ).count() == 2
    
    def test_non_constrained_actions(self):
        """Test that non-binary/non-mint actions have no unique constraints"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create multiple scoring_bonus entries (shouldn't be constrained)
        for i in range(3):
            HumanPoints.objects.create(
                address=address,
                action="scoring_bonus",
                points=500
            )
        
        # All should exist (though this shouldn't happen in practice)
        assert HumanPoints.objects.filter(
            address=address,
            action="scoring_bonus"
        ).count() == 3
    
    def test_address_length_constraint(self):
        """Test address field length constraint"""
        # Max length is 100 characters
        long_address = "0x" + "a" * 98  # Total 100 chars
        
        # This should work
        HumanPoints.objects.create(
            address=long_address,
            action="test_action",
            points=100
        )
        
        # This should fail - address too long
        too_long_address = "0x" + "a" * 99  # Total 101 chars
        with pytest.raises(DataError):
            HumanPoints.objects.create(
                address=too_long_address,
                action="test_action",
                points=100
            )
    
    def test_action_length_constraint(self):
        """Test action field length constraint"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Max length is 50 characters
        long_action = "a" * 50
        
        # This should work
        HumanPoints.objects.create(
            address=address,
            action=long_action,
            points=100
        )
        
        # This should fail - action too long
        too_long_action = "a" * 51
        with pytest.raises(DataError):
            HumanPoints.objects.create(
                address=address,
                action=too_long_action,
                points=100
            )
    
    def test_humanpointsprogramstats_primary_key(self):
        """Test that address is primary key for HumanPointProgramStats"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create first entry
        HumanPointProgramStats.objects.create(
            address=address,
            passing_scores=1
        )
        
        # Try to create duplicate - should fail
        with pytest.raises(IntegrityError):
            HumanPointProgramStats.objects.create(
                address=address,
                passing_scores=2
            )
    
    def test_humanpointsmultiplier_primary_key(self):
        """Test that address is primary key for HumanPointsMultiplier"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create first entry
        HumanPointsMultiplier.objects.create(
            address=address,
            multiplier=2
        )
        
        # Try to create duplicate - should fail
        with pytest.raises(IntegrityError):
            HumanPointsMultiplier.objects.create(
                address=address,
                multiplier=3
            )
    
    def test_null_tx_hash_allowed(self):
        """Test that tx_hash can be null for non-mint actions"""
        address = "0x1234567890123456789012345678901234567890"
        
        # Create entry without tx_hash
        points = HumanPoints.objects.create(
            address=address,
            action="human_keys",
            points=100
            # tx_hash not provided, should default to None
        )
        
        assert points.tx_hash is None
    
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