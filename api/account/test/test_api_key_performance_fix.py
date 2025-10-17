"""
Test suite for the API key performance fix.
Tests both SHA-256 and PBKDF2 fallback paths.
"""

import hashlib
import time
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.hashers import make_password
from django.test import TestCase, TransactionTestCase

from account.api_key_validator import FastAPIKeyValidator, averify_key
from account.models import Account, AccountAPIKey


class TestFastAPIKeyValidator(TestCase):
    """Test the FastAPIKeyValidator class."""

    def setUp(self):
        self.validator = FastAPIKeyValidator()
        # Test data from the API_KEY_PERFORMANCE_FIX.md document
        self.test_keys = [
            {
                "key": "s6x1cGkx.nB0WG3WarKxCEPqg8xZ224g5q7TlfanC",
                "prefix": "s6x1cGkx",
                "sha256_hash": "sha256$e51a53a646ac8430d5129ff4c8cbc7765a1d4e05bb83153e5bb4ac5e4aa0c56d",
            },
            {
                "key": "test1234.abcdefghijklmnopqrstuvwxyz123456",
                "prefix": "test1234",
                "sha256_hash": "sha256$6cc391d9cbb768a1c1ae1a27f585310c4270607a77bd79c23c1de3bb5476bf55",
            },
            {
                "key": "apikey01.verysecuresecretkey32charslong!",
                "prefix": "apikey01",
                "sha256_hash": "sha256$6e2847893205ab8b0dbb52620ca598a7d656318a8f38af4ed95530661831a51c",
            },
        ]

    def test_hash_key_generates_correct_sha256(self):
        """Test that hash_key generates the correct SHA-256 hash."""
        for test_data in self.test_keys:
            result = self.validator.hash_key(test_data["key"])
            self.assertEqual(result, test_data["sha256_hash"])

    def test_verify_key_with_sha256_fast_path(self):
        """Test verification using SHA-256 fast path."""
        key = self.test_keys[0]["key"]
        sha256_hash = self.test_keys[0]["sha256_hash"]

        # Test with hashed_key_sha256 provided
        is_valid, needs_migration = self.validator.verify_key(
            key=key,
            hashed_key="",  # Not used in this path
            hashed_key_sha256=sha256_hash
        )

        self.assertTrue(is_valid)
        self.assertFalse(needs_migration)

    def test_verify_key_with_wrong_sha256(self):
        """Test verification fails with incorrect SHA-256 hash."""
        key = self.test_keys[0]["key"]
        wrong_hash = self.test_keys[1]["sha256_hash"]  # Different key's hash

        is_valid, needs_migration = self.validator.verify_key(
            key=key,
            hashed_key="",
            hashed_key_sha256=wrong_hash
        )

        self.assertFalse(is_valid)
        self.assertFalse(needs_migration)

    def test_verify_key_with_pbkdf2_fallback(self):
        """Test verification using PBKDF2 fallback."""
        key = self.test_keys[0]["key"]
        # Generate a real PBKDF2 hash using Django's make_password
        pbkdf2_hash = make_password(key)

        is_valid, needs_migration = self.validator.verify_key(
            key=key,
            hashed_key=pbkdf2_hash,
            hashed_key_sha256=None
        )

        self.assertTrue(is_valid)
        self.assertTrue(needs_migration)  # Should indicate migration needed

    def test_verify_key_with_wrong_pbkdf2(self):
        """Test verification fails with incorrect PBKDF2 hash."""
        key = self.test_keys[0]["key"]
        wrong_pbkdf2_hash = make_password("wrongkey")

        is_valid, needs_migration = self.validator.verify_key(
            key=key,
            hashed_key=wrong_pbkdf2_hash,
            hashed_key_sha256=None
        )

        self.assertFalse(is_valid)
        self.assertFalse(needs_migration)

    def test_verify_key_with_sha256_in_hashed_key_field(self):
        """Test when SHA-256 is stored in hashed_key field (edge case)."""
        key = self.test_keys[0]["key"]
        sha256_hash = self.test_keys[0]["sha256_hash"]

        is_valid, needs_migration = self.validator.verify_key(
            key=key,
            hashed_key=sha256_hash,  # SHA-256 in legacy field
            hashed_key_sha256=None
        )

        self.assertTrue(is_valid)
        self.assertFalse(needs_migration)

    def test_verify_key_with_unknown_hash_format(self):
        """Test verification fails with unknown hash format."""
        key = self.test_keys[0]["key"]

        is_valid, needs_migration = self.validator.verify_key(
            key=key,
            hashed_key="unknown$format$hash",
            hashed_key_sha256=None
        )

        self.assertFalse(is_valid)
        self.assertFalse(needs_migration)

    def test_performance_difference(self):
        """Test that SHA-256 is significantly faster than PBKDF2."""
        key = self.test_keys[0]["key"]
        sha256_hash = self.test_keys[0]["sha256_hash"]
        pbkdf2_hash = make_password(key)

        # Time SHA-256 verification (100 iterations to get measurable time)
        start = time.perf_counter()
        for _ in range(100):
            self.validator.verify_key(key, "", sha256_hash)
        sha256_time = time.perf_counter() - start

        # Time PBKDF2 verification (just 1 iteration due to slowness)
        start = time.perf_counter()
        self.validator.verify_key(key, pbkdf2_hash, None)
        pbkdf2_time = time.perf_counter() - start

        # SHA-256 should be at least 1000x faster
        # (conservative estimate, actual speedup is ~25,000x)
        speedup = (pbkdf2_time * 100) / sha256_time
        self.assertGreater(speedup, 1000,
                          f"SHA-256 not fast enough. Speedup: {speedup:.1f}x")
        print(f"Performance test: SHA-256 is {speedup:.1f}x faster than PBKDF2")


class TestAsyncAPIKeyValidator(TestCase):
    """Test the async version of API key validator."""

    @pytest.mark.asyncio
    async def test_averify_key_with_sha256(self):
        """Test async verification with SHA-256."""
        key = "test1234.abcdefghijklmnopqrstuvwxyz123456"
        sha256_hash = "sha256$6cc391d9cbb768a1c1ae1a27f585310c4270607a77bd79c23c1de3bb5476bf55"

        is_valid, needs_migration = await averify_key(
            key=key,
            hashed_key="",
            hashed_key_sha256=sha256_hash
        )

        self.assertTrue(is_valid)
        self.assertFalse(needs_migration)

    @pytest.mark.asyncio
    async def test_averify_key_with_pbkdf2(self):
        """Test async verification with PBKDF2 fallback."""
        key = "test1234.abcdefghijklmnopqrstuvwxyz123456"
        pbkdf2_hash = make_password(key)

        is_valid, needs_migration = await averify_key(
            key=key,
            hashed_key=pbkdf2_hash,
            hashed_key_sha256=None
        )

        self.assertTrue(is_valid)
        self.assertTrue(needs_migration)


class TestAPIKeyMigration(TransactionTestCase):
    """Test the auto-migration functionality in a real database context."""

    def setUp(self):
        # Create a test user and account
        from django.contrib.auth import get_user_model
        User = get_user_model()

        self.user = User.objects.create_user(username="testuser")
        self.account = Account.objects.create(
            address="0x1234567890123456789012345678901234567890",
            user=self.user
        )

    @patch('account.models.AccountAPIKey.objects.get_from_key')
    def test_api_key_auto_migration(self, mock_get_from_key):
        """Test that API keys are auto-migrated on successful PBKDF2 verification."""
        # Create an API key with only PBKDF2 hash (simulating legacy key)
        key = "testkey1.secretsecretsecretsecretsecretsecret"
        prefix = "testkey1"

        # Create the API key manually (bypassing get_from_key)
        api_key = AccountAPIKey(
            prefix=prefix,
            name="Test Key",
            hashed_key=make_password(key),
            account=self.account,
            hashed_key_sha256=None  # No SHA-256 hash initially
        )
        api_key.save()

        # Verify the key doesn't have SHA-256 hash initially
        self.assertIsNone(api_key.hashed_key_sha256)

        # Simulate authentication with the validator
        validator = FastAPIKeyValidator()
        is_valid, needs_migration = validator.verify_key(
            key,
            api_key.hashed_key,
            api_key.hashed_key_sha256
        )

        self.assertTrue(is_valid)
        self.assertTrue(needs_migration)

        # Simulate the auto-migration that happens in authenticate()
        if needs_migration:
            api_key.hashed_key_sha256 = validator.hash_key(key)
            api_key.save(update_fields=['hashed_key_sha256'])

        # Reload and verify SHA-256 hash was saved
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.hashed_key_sha256)
        expected_hash = f"sha256${hashlib.sha256(key.encode()).hexdigest()}"
        self.assertEqual(api_key.hashed_key_sha256, expected_hash)

        # Verify subsequent authentication uses SHA-256 fast path
        is_valid, needs_migration = validator.verify_key(
            key,
            api_key.hashed_key,
            api_key.hashed_key_sha256
        )

        self.assertTrue(is_valid)
        self.assertFalse(needs_migration)  # No migration needed now