from unittest.mock import patch

from django.test import TestCase
from ninja.testing import TestClient

from internal.api import api_router as internal_api_router


class TestGetEmbedConfig(TestCase):
    def setUp(self):
        self.client = TestClient(internal_api_router)

    @patch("ceramic_cache.api.v1.handle_get_scorer_weights")
    @patch("embed.api.handle_get_embed_stamp_sections")
    def test_get_embed_config_with_sections(
        self, mock_get_sections, mock_get_weights
    ):
        """Test getting combined config with weights and stamp sections"""
        mock_get_weights.return_value = {"Google": 1.5, "Discord": 2.0}
        mock_get_sections.return_value = [
            {
                "title": "Identity Verification",
                "order": 0,
                "items": [
                    {"platform_id": "Binance", "order": 0},
                    {"platform_id": "Coinbase", "order": 1},
                ],
            }
        ]

        response = self.client.get("/embed/config?community_id=123")
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertIn("weights", result)
        self.assertIn("stamp_sections", result)
        self.assertEqual(result["weights"], {"Google": 1.5, "Discord": 2.0})
        self.assertEqual(len(result["stamp_sections"]), 1)
        self.assertEqual(result["stamp_sections"][0]["title"], "Identity Verification")

        mock_get_weights.assert_called_once_with("123")
        mock_get_sections.assert_called_once_with("123")

    @patch("ceramic_cache.api.v1.handle_get_scorer_weights")
    @patch("embed.api.handle_get_embed_stamp_sections")
    def test_get_embed_config_empty_sections(self, mock_get_sections, mock_get_weights):
        """Test getting config when no stamp sections are configured"""
        mock_get_weights.return_value = {"Google": 1.5}
        mock_get_sections.return_value = []

        response = self.client.get("/embed/config?community_id=456")
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(result["weights"], {"Google": 1.5})
        self.assertEqual(result["stamp_sections"], [])

    def test_get_embed_config_missing_community_id(self):
        """Test getting config without providing community_id"""
        response = self.client.get("/embed/config")
        self.assertEqual(response.status_code, 422)  # Unprocessable Entity

    @patch("ceramic_cache.api.v1.handle_get_scorer_weights")
    @patch("embed.api.handle_get_embed_stamp_sections")
    def test_get_embed_config_multiple_sections(
        self, mock_get_sections, mock_get_weights
    ):
        """Test getting config with multiple stamp sections"""
        mock_get_weights.return_value = {"Google": 1.5, "Discord": 2.0, "Github": 1.0}
        mock_get_sections.return_value = [
            {
                "title": "Identity Verification",
                "order": 0,
                "items": [
                    {"platform_id": "Binance", "order": 0},
                    {"platform_id": "Coinbase", "order": 1},
                ],
            },
            {
                "title": "Social Accounts",
                "order": 1,
                "items": [
                    {"platform_id": "Discord", "order": 0},
                    {"platform_id": "Github", "order": 1},
                    {"platform_id": "Google", "order": 2},
                ],
            },
        ]

        response = self.client.get("/embed/config?community_id=789")
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(len(result["stamp_sections"]), 2)
        self.assertEqual(result["stamp_sections"][0]["title"], "Identity Verification")
        self.assertEqual(result["stamp_sections"][1]["title"], "Social Accounts")
        self.assertEqual(len(result["stamp_sections"][1]["items"]), 3)


class TestGetEmbedWeightsDeprecated(TestCase):
    """Tests for the deprecated /embed/weights endpoint"""

    def setUp(self):
        self.client = TestClient(internal_api_router)

    @patch("internal.api.handle_get_scorer_weights")
    def test_deprecated_weights_endpoint_still_works(self, mock_get_weights):
        """Test that the deprecated weights endpoint still functions"""
        mock_get_weights.return_value = {"Google": 1.5, "Discord": 2.0}

        response = self.client.get("/embed/weights?community_id=123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"Google": 1.5, "Discord": 2.0})
