import json
from datetime import datetime, timezone
from typing import cast

from django.conf import settings
from django.test import Client, TestCase
from trusta_labs.models import TrustaLabsScore

mock_trusta_labs_score_body = {
    "address": "0x8u3eu3ydh3rydh3irydhu",
    "score": 20,
}


class TrustaLabsScoreTestCase(TestCase):
    def test_create_trusta_labs_score(self):
        self.headers = {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}
        """Test that creation of a trusta lab score works and saved correctly"""
        client = Client()
        trusta_labs_response = client.post(
            "/trusta_labs/trusta-labs-score",
            json.dumps(mock_trusta_labs_score_body),
            content_type="application/json",
            **self.headers
        )
        self.assertEqual(trusta_labs_response.status_code, 200)

        # Check that the trusta lab score was created
        all_trusta_labs_scores = list(TrustaLabsScore.objects.all())
        self.assertEqual(len(all_trusta_labs_scores), 1)
        score = all_trusta_labs_scores[0]
        self.assertEqual(score.address, mock_trusta_labs_score_body["address"])
        self.assertEqual(score.sybil_risk_score, mock_trusta_labs_score_body["score"])

    def test_error_creating_trusta_lab_score(self):
        pass
