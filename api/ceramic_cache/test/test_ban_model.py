from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from ceramic_cache.models import Ban


@pytest.fixture
def sample_address():
    return "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"


@pytest.fixture
def sample_hash():
    return "0x123abc..."


@pytest.fixture
def future_date():
    return timezone.now() + timedelta(days=7)


@pytest.fixture
def past_date():
    return timezone.now() - timedelta(days=7)


@pytest.mark.django_db
class TestBanModel:
    def test_create_ban_with_hash_only(self, sample_hash):
        """Test creating a ban with only a hash is valid"""
        ban = Ban(hash=sample_hash)
        ban.save()
        assert Ban.objects.count() == 1
        assert Ban.objects.first().hash == sample_hash

    def test_create_ban_with_address_only(self, sample_address):
        """Test creating a ban with only an address is valid"""
        ban = Ban(address=sample_address)
        ban.save()
        assert Ban.objects.count() == 1
        assert Ban.objects.first().address == sample_address.lower()

    def test_create_ban_with_address_and_provider(self, sample_address):
        """Test creating a ban with address and provider is valid"""
        ban = Ban(address=sample_address, provider="github")
        ban.save()
        assert Ban.objects.count() == 1
        assert Ban.objects.first().provider == "github"

    def test_create_invalid_ban_raises_error(self):
        """Test creating a ban without required fields raises ValidationError"""
        ban = Ban()
        with pytest.raises(ValidationError):
            ban.save()

    @pytest.mark.django_db
    class TestBanQueries:
        def test_get_bans_no_bans_exist(self, sample_address):
            """Test when no bans exist"""
            bans = Ban.get_bans(address=sample_address, hashes=["hash1", "hash2"])
            assert len(bans) == 0

        def test_get_bans_returns_all_relevant_bans(self, sample_address):
            """Test that get_bans returns all relevant bans in one query"""
            # Create various types of bans
            hash_ban = Ban.objects.create(hash="hash1")
            address_ban = Ban.objects.create(address=sample_address)
            provider_ban = Ban.objects.create(address=sample_address, provider="github")
            expired_ban = Ban.objects.create(
                address=sample_address, end_time=timezone.now() - timedelta(days=1)
            )

            # Query for bans
            bans = Ban.get_bans(address=sample_address, hashes=["hash1", "hash2"])

            # Should return hash ban, address ban, and provider ban (not expired ban)
            assert len(bans) == 3
            assert hash_ban in bans
            assert address_ban in bans
            assert provider_ban in bans
            assert expired_ban not in bans

        def test_check_credential_bans_hash_ban(self, sample_address):
            """Test checking a credential against a hash ban"""
            ban = Ban.objects.create(hash="hash1")
            bans = [ban]

            is_banned, ban_type, ban_obj = Ban.check_credential_bans(
                bans, sample_address, "hash1", "github"
            )

            assert is_banned
            assert ban_type == "hash"
            assert ban_obj == ban

        def test_check_credential_bans_provider_ban(self, sample_address):
            """Test checking a credential against a provider-specific ban"""
            ban = Ban.objects.create(address=sample_address, provider="github")
            bans = [ban]

            print("BAN", ban.__dict__)

            is_banned, ban_type, ban_obj = Ban.check_credential_bans(
                bans, sample_address, "hash1", "github"
            )

            assert is_banned
            assert ban_type == "single_stamp"
            assert ban_obj == ban

        def test_check_credential_bans_account_ban(self, sample_address):
            """Test checking a credential against an account-wide ban"""
            ban = Ban.objects.create(address=sample_address)
            bans = [ban]

            is_banned, ban_type, ban_obj = Ban.check_credential_bans(
                bans, sample_address, "hash1", "github"
            )

            assert is_banned
            assert ban_type == "account"
            assert ban_obj == ban

        def test_check_credential_bans_no_match(self, sample_address):
            """Test checking a credential against non-matching bans"""
            ban = Ban.objects.create(address="0x123different")
            bans = [ban]

            is_banned, ban_type, ban_obj = Ban.check_credential_bans(
                bans, sample_address, "hash1", "github"
            )

            assert not is_banned
            assert ban_type is None
            assert ban_obj is None

        def test_check_credential_bans_multiple_bans(self, sample_address):
            """Test that most specific ban type is returned when multiple apply"""
            hash_ban = Ban.objects.create(hash="hash1")
            address_ban = Ban.objects.create(address=sample_address)
            provider_ban = Ban.objects.create(address=sample_address, provider="github")
            bans = [address_ban, provider_ban, hash_ban]

            # Account ban should take precedence
            is_banned, ban_type, ban_obj = Ban.check_credential_bans(
                bans, sample_address, "hash1", "github"
            )
            assert is_banned
            assert ban_type == "account"
            assert ban_obj == address_ban

        def test_bulk_credential_check_workflow(self, sample_address):
            """Test the complete workflow of checking multiple credentials"""
            # Create some bans
            Ban.objects.create(hash="hash1")
            Ban.objects.create(address=sample_address, provider="github")

            # Get all bans in one query
            bans = Ban.get_bans(
                address=sample_address, hashes=["hash1", "hash2", "hash3"]
            )

            # Check multiple credentials
            credentials = [
                ("hash1", "twitter"),  # should be banned by hash
                ("hash2", "github"),  # should be banned by provider
                ("hash3", "twitter"),  # should not be banned
            ]

            results = []
            for hash, provider in credentials:
                is_banned, ban_type, ban = Ban.check_credential_bans(
                    bans, sample_address, hash, provider
                )
                results.append((is_banned, ban_type))

            assert results == [(True, "hash"), (True, "single_stamp"), (False, None)]
