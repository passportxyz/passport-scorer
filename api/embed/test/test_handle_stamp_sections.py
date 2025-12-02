from django.test import TestCase

from account.models import (
    Account,
    Community,
    Customization,
    EmbedStampSection,
    EmbedStampSectionItem,
)
from embed.api import handle_get_embed_stamp_sections


class TestHandleGetEmbedStampSections(TestCase):
    def setUp(self):
        # Create test account
        self.account = Account.objects.create(
            address="0x1234567890123456789012345678901234567890",
            user=None
        )
        
        # Create test community
        self.community = Community.objects.create(
            name="Test Community",
            account=self.account
        )
        
        # Create customization
        self.customization = Customization.objects.create(
            path="test-partner",
            scorer=self.community,
            partner_name="Test Partner"
        )

    def test_no_sections_returns_empty_list(self):
        """Test that when no sections are configured, empty list is returned"""
        result = handle_get_embed_stamp_sections(str(self.community.id))
        self.assertEqual(result, [])

    def test_sections_with_items(self):
        """Test that sections with items are returned correctly"""
        # Create sections
        section1 = EmbedStampSection.objects.create(
            customization=self.customization,
            title="Physical Verification",
            order=0
        )
        section2 = EmbedStampSection.objects.create(
            customization=self.customization,
            title="Web2 Platforms",
            order=1
        )
        
        # Create items for section1
        EmbedStampSectionItem.objects.create(
            section=section1,
            platform_id="Binance",
            order=0
        )
        EmbedStampSectionItem.objects.create(
            section=section1,
            platform_id="Coinbase",
            order=1
        )
        
        # Create items for section2
        EmbedStampSectionItem.objects.create(
            section=section2,
            platform_id="Discord",
            order=0
        )
        EmbedStampSectionItem.objects.create(
            section=section2,
            platform_id="Github",
            order=1
        )
        
        result = handle_get_embed_stamp_sections(str(self.community.id))
        
        # Verify structure
        self.assertEqual(len(result), 2)
        
        # Check first section
        self.assertEqual(result[0].title, "Physical Verification")
        self.assertEqual(result[0].order, 0)
        self.assertEqual(len(result[0].items), 2)
        self.assertEqual(result[0].items[0].platform_id, "Binance")
        self.assertEqual(result[0].items[1].platform_id, "Coinbase")
        
        # Check second section
        self.assertEqual(result[1].title, "Web2 Platforms")
        self.assertEqual(result[1].order, 1)
        self.assertEqual(len(result[1].items), 2)

    def test_sections_ordering(self):
        """Test that sections are returned in correct order"""
        # Create sections in reverse order
        section2 = EmbedStampSection.objects.create(
            customization=self.customization,
            title="Second Section",
            order=2
        )
        section1 = EmbedStampSection.objects.create(
            customization=self.customization,
            title="First Section",
            order=1
        )
        section0 = EmbedStampSection.objects.create(
            customization=self.customization,
            title="Zero Section",
            order=0
        )
        
        # Add at least one item to each section
        EmbedStampSectionItem.objects.create(
            section=section0,
            platform_id="Platform0",
            order=0
        )
        EmbedStampSectionItem.objects.create(
            section=section1,
            platform_id="Platform1",
            order=0
        )
        EmbedStampSectionItem.objects.create(
            section=section2,
            platform_id="Platform2",
            order=0
        )
        
        result = handle_get_embed_stamp_sections(str(self.community.id))
        
        # Verify ordering
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].title, "Zero Section")
        self.assertEqual(result[1].title, "First Section")
        self.assertEqual(result[2].title, "Second Section")

    def test_items_ordering_within_section(self):
        """Test that items within a section are ordered correctly"""
        section = EmbedStampSection.objects.create(
            customization=self.customization,
            title="Test Section",
            order=0
        )
        
        # Create items in reverse order
        EmbedStampSectionItem.objects.create(
            section=section,
            platform_id="Third",
            order=3
        )
        EmbedStampSectionItem.objects.create(
            section=section,
            platform_id="First",
            order=1
        )
        EmbedStampSectionItem.objects.create(
            section=section,
            platform_id="Second",
            order=2
        )
        
        result = handle_get_embed_stamp_sections(str(self.community.id))
        
        # Verify item ordering
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].items), 3)
        self.assertEqual(result[0].items[0].platform_id, "First")
        self.assertEqual(result[0].items[1].platform_id, "Second")
        self.assertEqual(result[0].items[2].platform_id, "Third")

    def test_nonexistent_community(self):
        """Test that nonexistent community returns empty list"""
        result = handle_get_embed_stamp_sections("99999")
        self.assertEqual(result, [])

    def test_community_without_customization(self):
        """Test that community without customization returns empty list"""
        # Create a community without customization
        community_no_custom = Community.objects.create(
            name="No Customization Community",
            account=self.account
        )
        
        result = handle_get_embed_stamp_sections(str(community_no_custom.id))
        self.assertEqual(result, [])

