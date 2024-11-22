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
    class TestCheckBan:
        def test_no_ban_exists(self, sample_address, sample_hash):
            """Test when no ban exists"""
            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert not is_banned
            assert message == ""

        def test_hash_ban(self, sample_address, sample_hash):
            """Test ban by credential hash"""
            Ban.objects.create(hash=sample_hash)
            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert is_banned
            assert "credential hash banned" in message

        def test_provider_specific_ban(self, sample_address, sample_hash):
            """Test ban by address for specific provider"""
            Ban.objects.create(address=sample_address, provider="github")
            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert is_banned
            assert "address banned for github" in message

        def test_provider_specific_ban_only_applies_to_provider(
            self, sample_address, sample_hash
        ):
            """Test ban by address for specific provider"""
            Ban.objects.create(address=sample_address, provider="github")
            is_banned, message = Ban.check_ban(
                provider="not_github", hash=sample_hash, address=sample_address
            )
            assert not is_banned

        def test_address_ban(self, sample_address, sample_hash):
            """Test ban by address for all providers"""
            Ban.objects.create(address=sample_address)
            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert is_banned
            assert "address banned" in message
            assert "for github" not in message

        def test_temporary_ban_active(self, sample_address, sample_hash, future_date):
            """Test temporary ban that's still active"""
            Ban.objects.create(address=sample_address, end_time=future_date)
            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert is_banned
            assert "days remaining" in message

        def test_temporary_ban_expired(self, sample_address, sample_hash, past_date):
            """Test temporary ban that has expired"""
            Ban.objects.create(address=sample_address, end_time=past_date)
            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert not is_banned
            assert message == ""

        def test_ban_with_reason(self, sample_address, sample_hash):
            """Test ban message includes reason when provided"""
            reason = "Very, very bad"
            Ban.objects.create(address=sample_address, reason=reason)
            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert is_banned
            assert reason in message

        def test_indefinite_ban_message(self, sample_address, sample_hash):
            """Test message for indefinite ban (no end_time)"""
            Ban.objects.create(address=sample_address)
            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert is_banned
            assert "Banned indefinitely" in message

        def test_multiple_bans_exists(self, sample_address, sample_hash):
            """Test when multiple bans exist, any active ban triggers banned status"""
            # Create expired ban
            Ban.objects.create(
                address=sample_address, end_time=timezone.now() - timedelta(days=1)
            )
            # Create active ban
            Ban.objects.create(hash=sample_hash)

            is_banned, message = Ban.check_ban(
                provider="github", hash=sample_hash, address=sample_address
            )
            assert is_banned
            assert "credential hash banned" in message
