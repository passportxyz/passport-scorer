from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from ceramic_cache.models import Ban, CeramicCache, Revocation


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
    @pytest.fixture
    def sample_stamp(self, sample_address):
        """Create a sample stamp"""
        return CeramicCache.objects.create(
            address=sample_address,
            provider="github",
            proof_value="proof1",
            stamp={"credentialSubject": {"hash": "hash1", "provider": "github"}},
        )

    @pytest.fixture
    def sample_stamps(self, sample_address):
        """Create multiple sample stamps"""
        stamps = []
        providers = ["github", "twitter", "discord"]
        hashes = ["hash1", "hash2", "hash3"]

        for i, (provider, hash) in enumerate(zip(providers, hashes)):
            stamps.append(
                CeramicCache.objects.create(
                    address=sample_address,
                    provider=provider,
                    proof_value=f"proof{i+1}",
                    stamp={"credentialSubject": {"hash": hash, "provider": provider}},
                )
            )
        return stamps

    # TODO: disabling hash ban for now
    # def test_create_ban_with_hash_only(self, sample_hash):
    #     """Test creating a ban with only a hash is valid"""
    #     ban = Ban(type="hash", hash=sample_hash)
    #     ban.save()
    #     assert Ban.objects.count() == 1
    #     assert Ban.objects.first().hash == sample_hash

    def test_create_ban_with_address_only(self, sample_address):
        """Test creating a ban with only an address is valid"""
        ban = Ban(type="account", address=sample_address)
        ban.save()
        assert Ban.objects.count() == 1
        assert Ban.objects.first().address == sample_address.lower()

    def test_create_ban_with_address_and_provider(self, sample_address):
        """Test creating a ban with address and provider is valid"""
        ban = Ban(type="single_stamp", address=sample_address, provider="github")
        ban.save()
        assert Ban.objects.count() == 1
        assert Ban.objects.first().provider == "github"

    def test_create_invalid_ban_raises_error(self):
        """Test creating a ban without required fields raises ValidationError"""
        ban = Ban()
        with pytest.raises(ValidationError):
            ban.save()

    def test_use_invalid_ban_type_raises_error(self):
        """Test creating a ban without valid ban type raises ValidationError"""
        ban = Ban(type="dummy")
        with pytest.raises(
            ValidationError,
            match="Invalid value in ban.type: 'dummy'. See `Wielding the Ban Hammer`.",
        ):
            ban.save()

    # TODO: disabling hash ban for now
    # def test_use_invalid_ban_with_type_hash_raises_error(self):
    #     """Test creating a hash ban with invalid hash raises ValidationError"""
    #     ban = Ban(type="hash")
    #     with pytest.raises(
    #         ValidationError,
    #         match="Invalid ban for type 'hash'. See `Wielding the Ban Hammer`.",
    #     ):
    #         ban.save()

    def test_use_invalid_ban_with_type_account_raises_error(self):
        """Test creating a hash ban with invalid account raises ValidationError"""
        ban = Ban(type="account")
        with pytest.raises(
            ValidationError,
            match="Invalid ban for type 'account'. See `Wielding the Ban Hammer`.",
        ):
            ban.save()

    def test_use_invalid_ban_with_type_single_stamp_raises_error(self, sample_address):
        """Test creating a hash ban with invalid single_stamp raises ValidationError"""
        with pytest.raises(
            ValidationError,
            match="Invalid ban for type 'single_stamp'. See `Wielding the Ban Hammer`.",
        ):
            Ban(type="single_stamp").save()
        with pytest.raises(
            ValidationError,
            match="Invalid ban for type 'single_stamp'. See `Wielding the Ban Hammer`.",
        ):
            Ban(type="single_stamp", address=sample_address).save()
        with pytest.raises(
            ValidationError,
            match="Invalid ban for type 'single_stamp'. See `Wielding the Ban Hammer`.",
        ):
            Ban(type="single_stamp", provider="Dummy").save()

    @pytest.mark.django_db
    class TestBanQueries:
        def test_get_bans_no_bans_exist(self, sample_address):
            """Test when no bans exist"""
            bans = Ban.get_bans(address=sample_address, hashes=["hash1", "hash2"])
            assert len(bans) == 0

        def test_get_bans_returns_all_relevant_bans(self, sample_address):
            """Test that get_bans returns all relevant bans in one query"""
            # Create various types of bans
            # TODO: disabling hash ban for now
            # hash_ban = Ban.objects.create(type="hash", hash="hash1")
            address_ban = Ban.objects.create(type="account", address=sample_address)
            provider_ban = Ban.objects.create(
                type="single_stamp", address=sample_address, provider="github"
            )
            expired_ban = Ban.objects.create(
                type="account",
                address=sample_address,
                end_time=timezone.now() - timedelta(days=1),
            )

            # Query for bans
            bans = Ban.get_bans(address=sample_address, hashes=["hash1", "hash2"])

            # Should return hash ban, address ban, and provider ban (not expired ban)
            assert len(bans) == 2
            # TODO: disabling hash ban for now
            # assert hash_ban in bans
            assert address_ban in bans
            assert provider_ban in bans
            assert expired_ban not in bans

        # TODO: disabling hash ban for now
        # def test_check_credential_bans_hash_ban(self, sample_address):
        #     """Test checking a credential against a hash ban"""
        #     ban = Ban.objects.create(type="hash", hash="hash1")
        #     bans = [ban]

        #     is_banned, ban_type, ban_obj = Ban.check_bans_for(
        #         bans, sample_address, "hash1", "github"
        #     )

        #     assert is_banned
        #     assert ban_type == "hash"
        #     assert ban_obj == ban

        def test_check_credential_bans_provider_ban(self, sample_address):
            """Test checking a credential against a provider-specific ban"""
            ban = Ban.objects.create(
                type="single_stamp", address=sample_address, provider="github"
            )
            bans = [ban]

            is_banned, ban_type, ban_obj = Ban.check_bans_for(
                bans, sample_address, "hash1", "github"
            )

            assert is_banned
            assert ban_type == "single_stamp"
            assert ban_obj == ban

        def test_check_credential_bans_account_ban(self, sample_address):
            """Test checking a credential against an account-wide ban"""
            ban = Ban.objects.create(type="account", address=sample_address)
            bans = [ban]

            is_banned, ban_type, ban_obj = Ban.check_bans_for(
                bans, sample_address, "hash1", "github"
            )

            assert is_banned
            assert ban_type == "account"
            assert ban_obj == ban

        def test_check_credential_bans_no_match(self, sample_address):
            """Test checking a credential against non-matching bans"""
            ban = Ban.objects.create(type="account", address="0x123different")
            bans = [ban]

            is_banned, ban_type, ban_obj = Ban.check_bans_for(
                bans, sample_address, "hash1", "github"
            )

            assert not is_banned
            assert ban_type is None
            assert ban_obj is None

        def test_check_credential_bans_multiple_bans(self, sample_address):
            """Test that most specific ban type is returned when multiple apply"""
            # TODO: disabling hash ban for now
            # hash_ban = Ban.objects.create(type="hash", hash="hash1")
            address_ban = Ban.objects.create(type="account", address=sample_address)
            provider_ban = Ban.objects.create(
                type="single_stamp", address=sample_address, provider="github"
            )
            bans = [
                address_ban,
                provider_ban,
                # TODO: disabling hash ban for now
                # hash_ban
            ]

            # Account ban should take precedence
            is_banned, ban_type, ban_obj = Ban.check_bans_for(
                bans, sample_address, "hash1", "github"
            )
            assert is_banned
            assert ban_type == "account"
            assert ban_obj == address_ban

        def test_bulk_credential_check_workflow(self, sample_address):
            """Test the complete workflow of checking multiple credentials"""
            # Create some bans
            # TODO: disabling hash ban for now
            # Ban.objects.create(type="hash", hash="hash1")
            Ban.objects.create(
                type="single_stamp", address=sample_address, provider="github"
            )

            # Get all bans in one query
            bans = Ban.get_bans(
                address=sample_address, hashes=["hash1", "hash2", "hash3"]
            )

            # Check multiple credentials
            credentials = [
                # TODO: disabling hash ban for now
                # ("hash1", "twitter"),  # should be banned by hash
                ("hash2", "github"),  # should be banned by provider
                ("hash3", "twitter"),  # should not be banned
            ]

            results = []
            for hash, provider in credentials:
                is_banned, ban_type, _ = Ban.check_bans_for(
                    bans, sample_address, hash, provider
                )
                results.append((is_banned, ban_type))

            assert results == [
                # TODO: disabling hash ban for now
                # (True, "hash"),
                (True, "single_stamp"),
                (False, None),
            ]

        # TODO: disabling hash ban for now
        # def test_revoke_matching_by_hash(self, sample_stamps):
        #     """Test revoking credentials by hash"""
        #     ban = Ban.objects.create(type="hash", hash="hash1")
        #     ban.revoke_matching_credentials()

        #     # Only the stamp with hash1 should be revoked
        #     assert Revocation.objects.count() == 1
        #     revocation = Revocation.objects.first()
        #     assert revocation.proof_value == "proof1"
        #     assert ban.last_run_revoke_matching is not None

        def test_revoke_matching_by_address(self, sample_stamps, sample_address):
            """Test revoking all credentials for an address"""
            ban = Ban.objects.create(type="account", address=sample_address)
            ban.revoke_matching_credentials()

            # All stamps for the address should be revoked
            assert Revocation.objects.count() == 3
            assert set(r.proof_value for r in Revocation.objects.all()) == {
                "proof1",
                "proof2",
                "proof3",
            }

        def test_revoke_matching_by_provider(self, sample_stamps, sample_address):
            """Test revoking credentials by provider"""
            ban = Ban.objects.create(
                type="single_stamp", address=sample_address, provider="github"
            )
            ban.revoke_matching_credentials()

            # Only github stamps should be revoked
            assert Revocation.objects.count() == 1
            revocation = Revocation.objects.first()
            assert revocation.ceramic_cache.provider == "github"

        def test_revoke_matching_already_revoked(self, sample_stamp):
            """Test attempting to revoke already revoked credentials"""
            # Create initial revocation
            Revocation.objects.create(
                proof_value=sample_stamp.proof_value, ceramic_cache=sample_stamp
            )
            print(" ~~~~~ sample_address: ", sample_address)
            ban = Ban.objects.create(type="account", address=sample_address)
            ban.revoke_matching_credentials()

            # Should still only be one revocation
            assert Revocation.objects.count() == 1

        def test_revoke_matching_deleted_stamps(self, sample_stamp, sample_address):
            """Test that deleted stamps are not revoked"""
            sample_stamp.deleted_at = timezone.now()
            sample_stamp.save()

            ban = Ban.objects.create(type="account", address=sample_address)
            ban.revoke_matching_credentials()

            assert Revocation.objects.count() == 0

        def test_revoke_matching_updates_timestamp(self, sample_stamp):
            """Test that last_run_revoke_matching is updated"""
            print(" ~~~~~ sample_address: ", sample_address)
            ban = Ban.objects.create(type="account", address=sample_address)
            assert ban.last_run_revoke_matching is None

            ban.revoke_matching_credentials()
            ban.refresh_from_db()

            assert ban.last_run_revoke_matching is not None
            assert ban.last_run_revoke_matching > ban.created_at

        def test_revoke_matching_no_matches(self):
            """Test revoking when no stamps match"""
            ban = Ban.objects.create(type="account", address="0xbad_address")
            ban.revoke_matching_credentials()

            assert Revocation.objects.count() == 0
            ban.refresh_from_db()
            assert ban.last_run_revoke_matching is not None
