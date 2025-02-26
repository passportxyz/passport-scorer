from unittest.mock import patch

from django.test import TestCase
from ninja.testing import TestClient

from internal.api import api_router as internal_api_router


class TestGetEmbedWeights(TestCase):
    def setUp(self):
        self.client = TestClient(internal_api_router)

    @patch("internal.api.handle_get_scorer_weights")
    def test_get_embed_weights_no_community(self, mock_handle_get_scorer_weights):
        mock_handle_get_scorer_weights.return_value = {"weight1": 0.5, "weight2": 1.0}

        response = self.client.get("/embed/weights")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"weight1": 0.5, "weight2": 1.0})
        mock_handle_get_scorer_weights.assert_called_once_with(None)

    @patch("internal.api.handle_get_scorer_weights")
    def test_get_embed_weights_with_community(self, mock_handle_get_scorer_weights):
        mock_handle_get_scorer_weights.return_value = {"weightA": 0.7, "weightB": 0.3}

        response = self.client.get("/embed/weights?community_id=community123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"weightA": 0.7, "weightB": 0.3})
        mock_handle_get_scorer_weights.assert_called_once_with("community123")
