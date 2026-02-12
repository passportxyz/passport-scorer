import json
from hashlib import sha256

import pytest
from django.contrib.auth import get_user_model

from account.models import (
    Account,
    Community,
    Customization,
    CustomCredential,
    CustomCredentialRuleset,
    CustomPlatform,
)

User = get_user_model()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="nft-test-user", password="12345")


@pytest.fixture
def test_account(test_user):
    return Account.objects.create(user=test_user, address="0xTESTADDRESS")


@pytest.fixture
def community(test_account):
    return Community.objects.create(
        name="test-community",
        description="Test community",
        account=test_account,
    )


@pytest.fixture
def customization(community):
    return Customization.objects.create(
        path="test-customization",
        scorer=community,
    )


@pytest.fixture
def nft_platform(db):
    return CustomPlatform.objects.create(
        name="TestNFTPlatform",
        platform_type="NFT",
        is_evm=True,
        display_name="Test NFT",
        description="Test NFT platform",
        icon_url="./assets/nft-icon.svg",
    )


@pytest.fixture
def devel_platform(db):
    return CustomPlatform.objects.create(
        name="TestDevelPlatform",
        platform_type="DEVEL",
        is_evm=False,
        display_name="Test Developer",
        description="Test developer platform",
        icon_url="./assets/devel-icon.svg",
    )


@pytest.fixture
def nft_ruleset(db):
    definition = {
        "name": "TestNFT",
        "condition": {
            "contracts": [
                {
                    "address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
                    "chainId": 1,
                    "standard": "ERC-721",
                }
            ]
        },
    }
    return CustomCredentialRuleset.objects.create(
        credential_type="NFT",
        definition=definition,
        name="TestNFT",
    )


@pytest.fixture
def devel_ruleset(db):
    definition = {
        "name": "TestDevel",
        "condition": {"allowList": ["0x1234"]},
    }
    return CustomCredentialRuleset.objects.create(
        credential_type="DEVEL",
        definition=definition,
        name="TestDevel",
    )


@pytest.mark.django_db
class TestNFTStamp:
    def test_nft_holder_provider_id_generation(self):
        """Provider ID should start with NFTHolder# and include definition hash."""
        definition = {
            "name": "BoredApes",
            "condition": {
                "contracts": [
                    {
                        "address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
                        "chainId": 1,
                        "standard": "ERC-721",
                    }
                ]
            },
        }
        ruleset = CustomCredentialRuleset.objects.create(
            credential_type="NFT",
            definition=definition,
            name="BoredApes",
        )
        assert ruleset.provider_id.startswith("NFTHolder#")
        # Verify full deterministic provider_id
        expected_hash = sha256(
            json.dumps(definition, sort_keys=True).encode("utf8")
        ).hexdigest()[0:8]
        assert ruleset.provider_id == f"NFTHolder#BoredApes#{expected_hash}"

    def test_get_custom_stamps_with_nft_platform(
        self, customization, nft_platform, nft_ruleset
    ):
        """get_custom_stamps should return platformType=NFT and isEVM=True."""
        CustomCredential.objects.create(
            customization=customization,
            platform=nft_platform,
            ruleset=nft_ruleset,
            weight=10.0,
            display_name="Test NFT Stamp",
            description="Test NFT description",
        )
        stamps = customization.get_custom_stamps()
        assert "TestNFTPlatform" in stamps
        platform_data = stamps["TestNFTPlatform"]
        assert platform_data["platformType"] == "NFT"
        assert platform_data["isEVM"] is True
        assert len(platform_data["credentials"]) == 1
        assert platform_data["credentials"][0]["providerId"] == nft_ruleset.provider_id

    def test_get_custom_stamps_developer_list_is_not_evm(
        self, customization, devel_platform, devel_ruleset
    ):
        """DeveloperList stamps should have isEVM=False (backward compatible)."""
        CustomCredential.objects.create(
            customization=customization,
            platform=devel_platform,
            ruleset=devel_ruleset,
            weight=5.0,
            display_name="Test Devel Stamp",
            description="Test devel description",
        )
        stamps = customization.get_custom_stamps()
        assert "TestDevelPlatform" in stamps
        platform_data = stamps["TestDevelPlatform"]
        assert platform_data["platformType"] == "DEVEL"
        assert platform_data["isEVM"] is False

    def test_get_custom_stamps_mixed_platform_types(
        self, customization, nft_platform, devel_platform, nft_ruleset, devel_ruleset
    ):
        """Both NFT and DeveloperList stamps on the same customization."""
        CustomCredential.objects.create(
            customization=customization,
            platform=nft_platform,
            ruleset=nft_ruleset,
            weight=10.0,
            display_name="NFT Stamp",
            description="NFT",
        )
        CustomCredential.objects.create(
            customization=customization,
            platform=devel_platform,
            ruleset=devel_ruleset,
            weight=5.0,
            display_name="Devel Stamp",
            description="Devel",
        )
        stamps = customization.get_custom_stamps()
        assert "TestNFTPlatform" in stamps
        assert "TestDevelPlatform" in stamps
        assert stamps["TestNFTPlatform"]["isEVM"] is True
        assert stamps["TestDevelPlatform"]["isEVM"] is False
        assert stamps["TestNFTPlatform"]["platformType"] == "NFT"
        assert stamps["TestDevelPlatform"]["platformType"] == "DEVEL"

    def test_dynamic_weights_include_nft_stamp(
        self, customization, nft_platform, nft_ruleset
    ):
        """get_customization_dynamic_weights should include NFT provider_id with weight."""
        CustomCredential.objects.create(
            customization=customization,
            platform=nft_platform,
            ruleset=nft_ruleset,
            weight=5.0,
            display_name="NFT Stamp",
            description="NFT",
        )
        weights = customization.get_customization_dynamic_weights()
        assert nft_ruleset.provider_id in weights
        assert weights[nft_ruleset.provider_id] == "5.0000"

    def test_nft_definition_with_multiple_contracts(self):
        """Ruleset with multiple contracts should save successfully."""
        definition = {
            "name": "MultiContract",
            "condition": {
                "contracts": [
                    {
                        "address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
                        "chainId": 1,
                        "standard": "ERC-721",
                    },
                    {
                        "address": "0x60E4d786628Fea6478F785A6d7e704777c86a7c6",
                        "chainId": 1,
                        "standard": "ERC-721",
                    },
                ]
            },
        }
        ruleset = CustomCredentialRuleset.objects.create(
            credential_type="NFT",
            definition=definition,
            name="MultiContract",
        )
        assert ruleset.pk is not None
        # Verify definition stored correctly
        ruleset.refresh_from_db()
        assert len(ruleset.definition["condition"]["contracts"]) == 2

    def test_nft_definition_without_contracts_key(self):
        """Ruleset without contracts key should save (validator is permissive).

        Documents that NFT-specific validation is deferred to IAM.
        """
        definition = {
            "name": "NoContracts",
            "condition": {},
        }
        ruleset = CustomCredentialRuleset.objects.create(
            credential_type="NFT",
            definition=definition,
            name="NoContracts",
        )
        assert ruleset.pk is not None

    def test_seed_migration_idempotency(self):
        """Running seed function twice should not raise IntegrityError."""
        import importlib

        from django.apps import apps

        migration_mod = importlib.import_module(
            "account.migrations.0054_seed_nft_holder_example"
        )
        seed_nft_example = migration_mod.seed_nft_example
        example_provider_id = migration_mod.EXAMPLE_PROVIDER_ID

        # Run seed twice - should use get_or_create, no error
        seed_nft_example(apps, None)
        seed_nft_example(apps, None)

        # Verify no duplicates
        assert CustomPlatform.objects.filter(name="NFTHolder").count() == 1
        assert (
            CustomCredentialRuleset.objects.filter(
                provider_id=example_provider_id
            ).count()
            == 1
        )
