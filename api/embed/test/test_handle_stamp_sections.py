from django.contrib.auth.models import User
from django.test import TestCase

from account.models import (
    Account,
    Community,
    Customization,
    EmbedSectionHeader,
    EmbedSectionOrder,
    EmbedStampPlatform,
)
from embed.api import handle_get_embed_config, handle_get_embed_stamp_sections
from registry.weight_models import (
    PlatformMetadata,
    WeightConfiguration,
    WeightConfigurationItem,
)
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS


def _get_or_create_platform(platform_id, name=None):
    """Helper to get or create a PlatformMetadata record for tests."""
    obj, _ = PlatformMetadata.objects.get_or_create(
        platform_id=platform_id,
        defaults={"name": name or platform_id},
    )
    return obj


class TestHandleGetEmbedStampSections(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")

        self.account = Account.objects.create(
            address="0x1234567890123456789012345678901234567890",
            user=self.user
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
            account=self.account
        )

        self.customization = Customization.objects.create(
            path="test-path",
            partner_name="Test Partner",
            scorer=self.community,
        )

    def test_no_sections_returns_empty_list(self):
        """Test that when no sections are configured, empty list is returned"""
        result = handle_get_embed_stamp_sections(str(self.community.id))
        self.assertEqual(result, [])

    def test_sections_with_items(self):
        """Test that sections with items are returned correctly"""
        header1 = EmbedSectionHeader.objects.create(name="Physical Verification")
        header2 = EmbedSectionHeader.objects.create(name="Web2 Platforms")

        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header1, order=0
        )
        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header2, order=1
        )

        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header1,
            platform=_get_or_create_platform("Binance"),
            order=0,
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header1,
            platform=_get_or_create_platform("Coinbase"),
            order=1,
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header2,
            platform=_get_or_create_platform("Discord"),
            order=0,
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header2,
            platform=_get_or_create_platform("Github", "GitHub"),
            order=1,
        )

        result = handle_get_embed_stamp_sections(str(self.community.id))

        self.assertEqual(len(result), 2)

        self.assertEqual(result[0].title, "Physical Verification")
        self.assertEqual(result[0].order, 0)
        self.assertEqual(len(result[0].items), 2)
        self.assertEqual(result[0].items[0].platform_id, "Binance")
        self.assertEqual(result[0].items[1].platform_id, "Coinbase")

        self.assertEqual(result[1].title, "Web2 Platforms")
        self.assertEqual(result[1].order, 1)
        self.assertEqual(len(result[1].items), 2)

    def test_sections_ordering(self):
        """Test that sections are returned in correct order"""
        header0 = EmbedSectionHeader.objects.create(name="Zero Section")
        header1 = EmbedSectionHeader.objects.create(name="First Section")
        header2 = EmbedSectionHeader.objects.create(name="Second Section")

        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header2, order=2
        )
        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header1, order=1
        )
        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header0, order=0
        )

        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header0,
            platform=_get_or_create_platform("Platform0"),
            order=0,
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header1,
            platform=_get_or_create_platform("Platform1"),
            order=0,
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header2,
            platform=_get_or_create_platform("Platform2"),
            order=0,
        )

        result = handle_get_embed_stamp_sections(str(self.community.id))

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].title, "Zero Section")
        self.assertEqual(result[1].title, "First Section")
        self.assertEqual(result[2].title, "Second Section")

    def test_items_ordering_within_section(self):
        """Test that items within a section are ordered correctly"""
        header = EmbedSectionHeader.objects.create(name="Test Section")
        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header, order=0
        )

        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header,
            platform=_get_or_create_platform("Third"),
            order=3,
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header,
            platform=_get_or_create_platform("First"),
            order=1,
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header,
            platform=_get_or_create_platform("Second"),
            order=2,
        )

        result = handle_get_embed_stamp_sections(str(self.community.id))

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].items), 3)
        self.assertEqual(result[0].items[0].platform_id, "First")
        self.assertEqual(result[0].items[1].platform_id, "Second")
        self.assertEqual(result[0].items[2].platform_id, "Third")

    def test_nonexistent_community(self):
        """Test that nonexistent community returns empty list"""
        result = handle_get_embed_stamp_sections("99999")
        self.assertEqual(result, [])

    def test_community_without_sections(self):
        """Test that community without sections returns empty list"""
        community_no_sections = Community.objects.create(
            name="No Sections Community",
            account=self.account
        )
        Customization.objects.create(
            path="no-sections-path",
            partner_name="No Sections",
            scorer=community_no_sections,
        )

        result = handle_get_embed_stamp_sections(str(community_no_sections.id))
        self.assertEqual(result, [])


class TestHandleGetEmbedConfig(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")

        self.account = Account.objects.create(
            address="0x1234567890123456789012345678901234567890",
            user=self.user
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
            account=self.account
        )

        self.customization = Customization.objects.create(
            path="config-test-path",
            partner_name="Config Test Partner",
            scorer=self.community,
        )

    def test_get_embed_config_returns_weights_and_sections(self):
        """Test that combined config returns both weights and stamp sections"""
        header = EmbedSectionHeader.objects.create(name="Test Section")
        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header, order=0
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header,
            platform=_get_or_create_platform("Google"),
            order=0,
        )

        result = handle_get_embed_config(str(self.community.id))

        self.assertIsNotNone(result.weights)
        self.assertIsInstance(result.weights, dict)

        self.assertEqual(len(result.stamp_sections), 1)
        self.assertEqual(result.stamp_sections[0].title, "Test Section")

    def test_get_embed_config_empty_sections(self):
        """Test that config returns empty sections when none configured"""
        result = handle_get_embed_config(str(self.community.id))

        self.assertIsNotNone(result.weights)
        self.assertEqual(result.stamp_sections, [])

    def test_get_embed_config_with_multiple_sections(self):
        """Test config with multiple sections and items"""
        header1 = EmbedSectionHeader.objects.create(name="Section One")
        header2 = EmbedSectionHeader.objects.create(name="Section Two")

        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header1, order=0
        )
        EmbedSectionOrder.objects.create(
            customization=self.customization, section=header2, order=1
        )

        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header1,
            platform=_get_or_create_platform("Google"),
            order=0,
        )
        EmbedStampPlatform.objects.create(
            customization=self.customization,
            section=header2,
            platform=_get_or_create_platform("Discord"),
            order=0,
        )

        result = handle_get_embed_config(str(self.community.id))

        self.assertEqual(len(result.stamp_sections), 2)
        self.assertEqual(result.stamp_sections[0].title, "Section One")
        self.assertEqual(result.stamp_sections[1].title, "Section Two")
