"""Tests for custom stamps platform definitions in embed config.

Tests cover all supported combinations:
A. CustomPlatform with single CustomCredential
B. CustomPlatform with multiple CustomCredentials
C. CustomPlatform with single AllowList
D. CustomPlatform with mixed credentials (AllowList + CustomCredential)
E. Standalone AllowList (no CustomPlatform)
F. Multiple CustomPlatforms on same Customization
G. No custom stamps at all
"""

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
from embed.api import (
    handle_get_embed_config,
    handle_get_platforms,
)
from registry.weight_models import (
    WeightConfiguration,
    WeightConfigurationItem,
)
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS


class TestHandleGetPlatforms(TestCase):
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

    def _make_platform(self, name, platform_type=CustomPlatform.PlatformType.DeveloperList, **kwargs):
        return CustomPlatform.objects.create(
            platform_type=platform_type,
            name=name,
            **kwargs,
        )

    def _make_ruleset(self, definition_name, credential_type=CustomCredentialRuleset.CredentialType.DeveloperList):
        return CustomCredentialRuleset.objects.create(
            credential_type=credential_type,
            definition={"name": definition_name, "condition": {"AND": []}},
            name=definition_name,
            provider_id=f"placeholder_{definition_name}",  # overwritten by save()
        )

    def _make_credential(self, platform, ruleset, weight=1.0, display_name=None, description=None):
        return CustomCredential.objects.create(
            customization=self.customization,
            platform=platform,
            ruleset=ruleset,
            weight=weight,
            display_name=display_name or ruleset.name,
            description=description,
        )

    def _make_allow_list(self, list_name, weight=10.0, platform=None):
        addr_list = AddressList.objects.create(name=list_name)
        return AllowList.objects.create(
            address_list=addr_list,
            customization=self.customization,
            weight=weight,
            platform=platform,
        )

    # --- A: CustomPlatform with single CustomCredential ---

    def test_single_credential_platform(self):
        """A single DeveloperList credential under a CustomPlatform."""
        platform = self._make_platform("PassportDeveloper", display_name="Passport Developer")
        ruleset = self._make_ruleset("PassportContributor")
        self._make_credential(platform, ruleset, weight=1.5)

        result = handle_get_platforms(str(self.community.id))
        self.assertEqual(len(result), 1)
        pdef = result[0]
        self.assertEqual(pdef.platform_id, "PassportDeveloper")
        self.assertEqual(pdef.icon_platform_id, "CustomGithub")
        self.assertEqual(pdef.name, "Passport Developer")
        self.assertFalse(pdef.is_evm)
        self.assertTrue(pdef.requires_signature)
        self.assertTrue(pdef.requires_popup)
        self.assertEqual(len(pdef.credentials), 1)
        self.assertTrue(pdef.credentials[0].id.startswith("DeveloperList#PassportContributor#"))
        self.assertEqual(pdef.credentials[0].weight, "1.5")

    # --- B: CustomPlatform with multiple CustomCredentials ---

    def test_multi_credential_platform(self):
        """Two credentials grouped under the same CustomPlatform."""
        platform = self._make_platform("ZKDeveloper", display_name="ZK Developer")
        ruleset1 = self._make_ruleset("ZkDeveloper")
        ruleset2 = self._make_ruleset("ZkOrPassportDeveloper")
        self._make_credential(platform, ruleset1, weight=1.0)
        self._make_credential(platform, ruleset2, weight=1.0)

        result = handle_get_platforms(str(self.community.id))
        self.assertEqual(len(result), 1)
        pdef = result[0]
        self.assertEqual(pdef.platform_id, "ZKDeveloper")
        self.assertEqual(pdef.name, "ZK Developer")
        self.assertEqual(len(pdef.credentials), 2)
        cred_ids = {c.id for c in pdef.credentials}
        self.assertTrue(any(c.startswith("DeveloperList#ZkDeveloper#") for c in cred_ids))
        self.assertTrue(any(c.startswith("DeveloperList#ZkOrPassportDeveloper#") for c in cred_ids))

    # --- C: CustomPlatform with single AllowList ---

    def test_allow_list_under_platform(self):
        """An AllowList grouped under a CustomPlatform."""
        platform = self._make_platform("OctantMembers", display_name="Octant Members")
        self._make_allow_list("OctantFinal", weight=21.0, platform=platform)

        result = handle_get_platforms(str(self.community.id))
        self.assertEqual(len(result), 1)
        pdef = result[0]
        self.assertEqual(pdef.platform_id, "OctantMembers")
        self.assertEqual(pdef.name, "Octant Members")
        self.assertEqual(len(pdef.credentials), 1)
        self.assertEqual(pdef.credentials[0].id, "AllowList#OctantFinal")
        self.assertEqual(pdef.credentials[0].weight, "21.0")

    # --- D: CustomPlatform with mixed credentials ---

    def test_mixed_credentials_platform(self):
        """One platform combining AllowList + CustomCredential."""
        platform = self._make_platform(
            "OctantVIP",
            platform_type=CustomPlatform.PlatformType.NFTHolder,
            display_name="Octant VIP",
            is_evm=True,
        )
        ruleset = self._make_ruleset(
            "Covenant",
            credential_type=CustomCredentialRuleset.CredentialType.NFTHolder,
        )
        self._make_credential(platform, ruleset, weight=4.0)
        self._make_allow_list("OctantFinal", weight=21.0, platform=platform)

        result = handle_get_platforms(str(self.community.id))
        self.assertEqual(len(result), 1)
        pdef = result[0]
        self.assertEqual(pdef.platform_id, "OctantVIP")
        self.assertEqual(pdef.icon_platform_id, "NFT")
        self.assertTrue(pdef.is_evm)
        self.assertEqual(len(pdef.credentials), 2)
        cred_ids = {c.id for c in pdef.credentials}
        self.assertTrue(any(c.startswith("NFTHolder#Covenant#") for c in cred_ids))
        self.assertIn("AllowList#OctantFinal", cred_ids)

    # --- E: Standalone AllowList (no CustomPlatform) ---

    def test_standalone_allow_list(self):
        """AllowList with no platform becomes its own platform entry."""
        self._make_allow_list("VIPList", weight=10.0, platform=None)

        result = handle_get_platforms(str(self.community.id))
        self.assertEqual(len(result), 1)
        pdef = result[0]
        self.assertEqual(pdef.platform_id, "AllowList#VIPList")
        self.assertEqual(pdef.icon_platform_id, "AllowList")
        self.assertEqual(pdef.name, "VIPList")
        self.assertFalse(pdef.is_evm)
        self.assertFalse(pdef.requires_signature)
        self.assertFalse(pdef.requires_popup)
        self.assertEqual(len(pdef.credentials), 1)
        self.assertEqual(pdef.credentials[0].id, "AllowList#VIPList")
        self.assertEqual(pdef.credentials[0].weight, "10.0")

    # --- F: Multiple CustomPlatforms ---

    def test_multiple_platforms(self):
        """Two separate CustomPlatforms on the same customization."""
        platform1 = self._make_platform(
            "Covenant",
            platform_type=CustomPlatform.PlatformType.NFTHolder,
            display_name="Covenant",
            is_evm=True,
        )
        platform2 = self._make_platform(
            "BoredApe",
            platform_type=CustomPlatform.PlatformType.NFTHolder,
            display_name="Bored Ape",
            is_evm=True,
        )
        ruleset1 = self._make_ruleset("Covenant", CustomCredentialRuleset.CredentialType.NFTHolder)
        ruleset2 = self._make_ruleset("LucianTest", CustomCredentialRuleset.CredentialType.NFTHolder)
        self._make_credential(platform1, ruleset1, weight=4.0)
        self._make_credential(platform2, ruleset2, weight=5.0)

        result = handle_get_platforms(str(self.community.id))
        self.assertEqual(len(result), 2)
        ids = {p.platform_id for p in result}
        self.assertEqual(ids, {"Covenant", "BoredApe"})
        for pdef in result:
            self.assertTrue(pdef.is_evm)
            self.assertEqual(pdef.icon_platform_id, "NFT")
            self.assertEqual(len(pdef.credentials), 1)

    # --- G: No custom stamps at all ---

    def test_no_custom_stamps(self):
        """Customization with no custom stamps returns empty platforms."""
        result = handle_get_platforms(str(self.community.id))
        self.assertEqual(result, [])

    def test_nonexistent_community(self):
        result = handle_get_platforms("99999")
        self.assertEqual(result, [])

    # --- Config integration ---

    def test_embed_config_returns_platforms(self):
        """handle_get_embed_config includes platforms and no custom_stamps field."""
        platform = self._make_platform("TestPlatform", display_name="Test")
        ruleset = self._make_ruleset("TestCred")
        self._make_credential(platform, ruleset, weight=2.0)
        self._make_allow_list("GuestList", weight=1.0, platform=None)

        result = handle_get_embed_config(str(self.community.id))

        # Has platforms
        self.assertEqual(len(result.platforms), 2)
        platform_ids = {p.platform_id for p in result.platforms}
        self.assertIn("TestPlatform", platform_ids)
        self.assertIn("AllowList#GuestList", platform_ids)

        # Has weights
        self.assertIsInstance(result.weights, dict)

        # No custom_stamps field
        self.assertFalse(hasattr(result, "custom_stamps"))

    def test_embed_config_no_auto_appended_sections(self):
        """Stamp sections no longer auto-appended by embed config."""
        self._make_allow_list("GuestList", weight=1.0, platform=None)

        result = handle_get_embed_config(str(self.community.id))

        # No auto-appended sections (stamp_sections comes from admin config only)
        guest_sections = [s for s in result.stamp_sections if s.title == "Guest List"]
        self.assertEqual(len(guest_sections), 0)
