from unittest.mock import patch

from django.test import TestCase
from ninja.testing import TestClient

from internal.api import api_router as internal_api_router


class TestGetEmbedStampSections(TestCase):
    def setUp(self):
        self.client = TestClient(internal_api_router)

    @patch("internal.api.handle_get_embed_stamp_sections")
    def test_get_embed_stamp_sections_empty(self, mock_handle_get_embed_stamp_sections):
        """Test getting stamp sections when none are configured"""
        mock_handle_get_embed_stamp_sections.return_value = []

        response = self.client.get("/embed/stamp-sections?community_id=123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        mock_handle_get_embed_stamp_sections.assert_called_once_with("123")

    @patch("internal.api.handle_get_embed_stamp_sections")
    def test_get_embed_stamp_sections_with_data(self, mock_handle_get_embed_stamp_sections):
        """Test getting stamp sections with customized data"""
        mock_sections = [
            {
                "title": "Identity Verification",
                "order": 0,
                "items": [
                    {"platform_id": "Binance", "order": 0},
                    {"platform_id": "Coinbase", "order": 1},
                ]
            },
            {
                "title": "Social Accounts",
                "order": 1,
                "items": [
                    {"platform_id": "Discord", "order": 0},
                    {"platform_id": "Github", "order": 1},
                    {"platform_id": "Google", "order": 2},
                ]
            }
        ]
        mock_handle_get_embed_stamp_sections.return_value = mock_sections

        response = self.client.get("/embed/stamp-sections?community_id=456")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        # Verify structure
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "Identity Verification")
        self.assertEqual(result[0]["order"], 0)
        self.assertEqual(len(result[0]["items"]), 2)
        self.assertEqual(result[1]["title"], "Social Accounts")
        self.assertEqual(len(result[1]["items"]), 3)
        
        mock_handle_get_embed_stamp_sections.assert_called_once_with("456")

    @patch("internal.api.handle_get_embed_stamp_sections")
    def test_get_embed_stamp_sections_missing_community_id(self, mock_handle_get_embed_stamp_sections):
        """Test getting stamp sections without providing community_id"""
        response = self.client.get("/embed/stamp-sections")
        # The endpoint requires community_id, so this should fail
        self.assertEqual(response.status_code, 422)  # Unprocessable Entity

