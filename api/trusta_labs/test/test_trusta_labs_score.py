import json

from django.conf import settings
from django.test import Client, TestCase
from registry.models import Event

mock_trusta_labs_score_body = {
    "address": "0x8u3eu3ydh3rydh3irydhu",
    "score": 20,
}


class TrustaLabsScoreTestCase(TestCase):
    def test_create_trusta_labs_score(self):
        """Test that creation of a trusta lab score works and saved correctly"""
        self.headers = {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}
        client = Client()
        trusta_labs_response = client.post(
            "/trusta_labs/trusta-labs-score",
            json.dumps(mock_trusta_labs_score_body),
            content_type="application/json",
            **self.headers
        )
        self.assertEqual(trusta_labs_response.status_code, 200)

        # Check that the trusta lab score was created
        all_trusta_labs_scores = list(
            Event.objects.filter(action=Event.Action.TRUSTALAB_SCORE)
        )
        self.assertEqual(len(all_trusta_labs_scores), 1)
        score = all_trusta_labs_scores[0]
        self.assertEqual(score.address, mock_trusta_labs_score_body["address"])
        self.assertEqual(score.data["score"], mock_trusta_labs_score_body["score"])

    def test_error_creating_trusta_lab_score(self):
        self.headers = {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}
        client = Client()
        trusta_labs_response = client.post(
            "/trusta_labs/trusta-labs-score",
            "{}",
            content_type="application/json",
            **self.headers
        )
        self.assertEqual(trusta_labs_response.status_code, 422)

        # Check that the trusta lab score was not created
        all_trusta_labs_scores = list(
            Event.objects.filter(action=Event.Action.TRUSTALAB_SCORE)
        )
        self.assertEqual(len(all_trusta_labs_scores), 0)

    def test_bad_auth(self):
        self.headers = {"HTTP_AUTHORIZATION": "bad_auth"}
        client = Client()
        trusta_labs_response = client.post(
            "/trusta_labs/trusta-labs-score",
            "{}",
            content_type="application/json",
            **self.headers
        )
        self.assertEqual(trusta_labs_response.status_code, 401)

        # Check that the trusta lab score was not created
        all_trusta_labs_scores = list(
            Event.objects.filter(action=Event.Action.TRUSTALAB_SCORE)
        )
        self.assertEqual(len(all_trusta_labs_scores), 0)
