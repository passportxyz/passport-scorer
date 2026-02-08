"""Tests for custom stamps (AllowList / Guest List and Developer List) in embed config."""

from django.contrib.auth.models import User
from django.test import TestCase

from account.models import (
    Account,
    AddressList,
    AllowList,
    Community,
    CustomCredential,
    CustomCredentialRuleset,
    Customization,
    CustomPlatform,
)
from embed.api import handle_get_custom_stamps, handle_get_embed_config
from registry.weight_models import (
    PlatformMetadata,
    WeightConfiguration,
    WeightConfigurationItem,
)
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS


class TestHandleGetCustomStamps(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.account = Account.objects.create(
            address="0x1234567890123456789012345678901234567890",
            user=self.user,
        )

        config = WeightConfiguration.objects.create(
            version="v1",
            threshold=5.0,
            active=True,
            description="Test",
        )
        for provider, weight in GITCOIN_PASSPORT_WEIGHTS.items():
            WeightConfigurationItem.objects.create(
                weight_configuration=config,
                provider=provider,
                weight=float(weight),
            )

        self.community = Community.objects.create(
            name="Test Community",
            account=self.account,
        )
        self.customization = Customization.objects.create(
            path="test-custom-stamps",
            partner_name="Test Partner",
            scorer=self.community,
        )

    def test_no_custom_stamps_returns_empty(self):
        result = handle_get_custom_stamps(str(self.community.id))
        self.assertEqual(result.allow_list_stamps, [])
        self.assertEqual(result.developer_list_stamps, [])

    def test_allow_list_stamps_returned(self):
        addr_list = AddressList.objects.create(name="VIPList")
        AllowList.objects.create(
            address_list=addr_list,
            customization=self.customization,
            weight=10.0,
        )

        result = handle_get_custom_stamps(str(self.community.id))
        self.assertEqual(len(result.allow_list_stamps), 1)
        self.assertEqual(result.allow_list_stamps[0].provider_id, "AllowList#VIPList")
        self.assertEqual(result.allow_list_stamps[0].display_name, "VIPList")
        self.assertEqual(result.allow_list_stamps[0].weight, 10.0)
        self.assertEqual(len(result.developer_list_stamps), 0)

    def test_developer_list_stamps_returned(self):
        platform = CustomPlatform.objects.create(
            platform_type=CustomPlatform.PlatformType.DeveloperList,
            name="custom_github",
            display_name="Developer List",
        )
        ruleset = CustomCredentialRuleset.objects.create(
            credential_type=CustomCredentialRuleset.CredentialType.DeveloperList,
            definition={
                "name": "TestRepo",
                "condition": {"AND": []},
            },
            name="TestRepo",
            provider_id="DeveloperList#TestRepo#placeholder",  # overwritten by save()
        )
        CustomCredential.objects.create(
            customization=self.customization,
            platform=platform,
            ruleset=ruleset,
            weight=5.0,
            display_name="Test Repo Contributor",
            description="Verify contributions to TestRepo",
        )

        result = handle_get_custom_stamps(str(self.community.id))
        self.assertEqual(len(result.allow_list_stamps), 0)
        self.assertEqual(len(result.developer_list_stamps), 1)
        self.assertTrue(
            result.developer_list_stamps[0].provider_id.startswith("DeveloperList#TestRepo#"),
            msg=f"provider_id should start with DeveloperList#TestRepo#, got {result.developer_list_stamps[0].provider_id}",
        )
        self.assertEqual(
            result.developer_list_stamps[0].display_name,
            "Test Repo Contributor",
        )
        self.assertEqual(
            result.developer_list_stamps[0].description,
            "Verify contributions to TestRepo",
        )
        self.assertEqual(result.developer_list_stamps[0].weight, 5.0)

    def test_embed_config_includes_custom_stamps(self):
        addr_list = AddressList.objects.create(name="GuestList")
        AllowList.objects.create(
            address_list=addr_list,
            customization=self.customization,
            weight=1.0,
        )

        result = handle_get_embed_config(str(self.community.id))
        self.assertIsNotNone(result.custom_stamps)
        self.assertEqual(len(result.custom_stamps.allow_list_stamps), 1)
        self.assertEqual(
            result.custom_stamps.allow_list_stamps[0].provider_id,
            "AllowList#GuestList",
        )
        self.assertEqual(len(result.custom_stamps.developer_list_stamps), 0)

    def test_nonexistent_community_returns_empty_custom_stamps(self):
        result = handle_get_custom_stamps("99999")
        self.assertEqual(result.allow_list_stamps, [])
        self.assertEqual(result.developer_list_stamps, [])
