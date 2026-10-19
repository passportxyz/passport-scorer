"""Linked wallets stay private (holonym-foundation/internal-docs#3587).

A group score must not tell an API caller which wallets are linked. Only keys
with ``linked_wallet_breakdown`` (WaaP's own key) see ``linked_score`` and
``source_wallet``. These tests run the real group path through the public
endpoint; only the linkage lookup and per-wallet stamp scoring are faked.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase

from account.models import Account, AccountAPIKey, Community
from embed.api import handle_get_score
from registry.models import Event, Score
from scorer_weighted.models import BinaryWeightedScorer, Scorer

W = "0x" + "1" * 40  # asks first, so it becomes canonical
A = "0x" + "a" * 40  # linked to W
GROUP = [W, A]

EXPIRES = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def stamp(score: str, dedup: bool = False) -> dict:
    return {"score": score, "dedup": dedup, "expiration_date": EXPIRES}


# Each wallet's own scoring: W holds Google; A holds Twitter, and its Google is
# a duplicate of W's. The group adds up to 25, over the threshold of 20.
OWN_STAMPS = {
    W: ({"Google": stamp("10.00000")}, {"Google": "10"}),
    A: (
        {"Twitter": stamp("15.00000"), "Google": stamp("0.00000", dedup=True)},
        {"Twitter": "15"},
    ),
}


async def fake_ascore_passport(community, passport, address, score):
    stamps, stamp_scores = OWN_STAMPS[address]
    raw = sum(Decimal(v) for v in stamp_scores.values())
    score.stamps = stamps
    score.stamp_scores = stamp_scores
    score.score = Decimal(1) if raw >= 20 else Decimal(0)
    score.evidence = {
        "type": "ThresholdScoreCheck",
        "success": raw >= 20,
        "rawScore": str(raw),
        "threshold": "20",
    }
    score.status = Score.Status.DONE
    score.last_score_timestamp = datetime.now(timezone.utc)
    score.expiration_date = datetime.fromisoformat(EXPIRES)


async def linked_group(address):
    return GROUP if address in GROUP else [address]


@patch("v2.api.api_stamps.ascore_passport", side_effect=fake_ascore_passport)
@patch("v2.api.api_stamps.get_linked_addresses", side_effect=linked_group)
class TestLinkedWalletPrivacy(TransactionTestCase):
    def setUp(self):
        user = User.objects.create_user(username="linked", password="12345")
        account = Account.objects.create(user=user, address="0x" + "9" * 40)
        scorer = BinaryWeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED_BINARY,
            threshold=Decimal("20"),
            weights={"Google": "10", "Twitter": "15"},
        )
        self.community = Community.objects.create(
            name="Linked", description="Linked", account=account, scorer=scorer
        )
        _, self.secret = AccountAPIKey.objects.create_key(
            account=account, name="partner"
        )
        _, self.waap_secret = AccountAPIKey.objects.create_key(
            account=account, name="waap", linked_wallet_breakdown=True
        )
        self.client = Client()

    def get_score(self, address, secret=None):
        response = self.client.get(
            f"/v2/stamps/{self.community.pk}/score/{address}",
            HTTP_AUTHORIZATION=f"Token {secret or self.secret}",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def assert_names_only(self, body: str, address: str):
        """No address from the group other than the one asked about."""
        for other in GROUP:
            if other != address:
                self.assertNotIn(other, body.lower())
        self.assertNotIn("source_wallet", body)
        self.assertNotIn("wallet_stamps", body)

    def test_canonical_wallet_hides_the_group(self, *_):
        response = self.get_score(W)

        body = response.json()
        self.assertEqual(body["score"], "25.00000")  # Google 10 + Twitter 15
        self.assertTrue(body["passing_score"])
        self.assertEqual(set(body["stamps"]), {"Google", "Twitter"})
        self.assertIsNone(body["linked_score"])
        self.assert_names_only(response.content.decode(), W)

    def test_linked_wallet_hides_the_group(self, *_):
        self.get_score(W)  # W becomes canonical
        response = self.get_score(A)

        body = response.json()
        self.assertEqual(body["score"], "0.00000")
        self.assertEqual(body["stamps"], {})
        self.assertIsNone(body["linked_score"])
        self.assert_names_only(response.content.decode(), A)

    def test_saved_score_and_events_hold_no_other_wallet(self, *_):
        self.get_score(W)

        row = Score.objects.get(passport__address=W)
        self.assertNotIn(A, json.dumps(row.stamps).lower())
        events = Event.objects.filter(action=Event.Action.SCORE_UPDATE, address=W)
        self.assertTrue(events.exists())
        for event in events:
            self.assertNotIn(A, json.dumps(event.data).lower())

    def test_embed_score_hides_the_group(self, *_):
        self.get_score(W)

        response = handle_get_score(str(self.community.pk), A)

        self.assertIsNone(response.score.linked_score)
        self.assert_names_only(response.score.model_dump_json(), A)

    def test_breakdown_key_sees_the_group(self, *_):
        body = self.get_score(W, self.waap_secret).json()

        self.assertEqual(body["stamps"]["Twitter"]["source_wallet"], A)
        self.assertEqual(body["stamps"]["Google"]["source_wallet"], W)
        linked = body["linked_score"]
        self.assertEqual(linked["address"], W)
        self.assertEqual(set(linked["wallet_stamps"]), {W, A})

    def test_breakdown_lists_each_wallets_own_stamps(self, *_):
        """W's entry is W's own scoring, not the merged group."""
        body = self.get_score(W, self.waap_secret).json()

        wallet_stamps = body["linked_score"]["wallet_stamps"]
        self.assertEqual(set(wallet_stamps[W]), {"Google"})
        self.assertEqual(set(wallet_stamps[A]), {"Twitter", "Google"})
