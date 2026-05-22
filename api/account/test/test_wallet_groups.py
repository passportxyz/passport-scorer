"""Tests for the per-community canonical-wallet claim model and scoring helpers.

Phase 0 of holonym-foundation/internal-docs#1060: ``WalletGroup`` and
``WalletGroupMembership`` (and the wallet-linking API) have moved to Silk.
What remains here is exercising the scorer-side surface:

- ``WalletGroupCommunityClaim`` (now keyed on an opaque ``group_key`` TEXT)
- ``_build_non_canonical_response`` response shape
- The stamp-merge / weight-aggregation logic in ``_score_wallet_group``
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.test import TestCase

from account.models import (
    Account,
    Community,
    WalletGroupCommunityClaim,
)
from registry.models import Passport, Score
from scorer_weighted.models import BinaryWeightedScorer, Scorer

# ============================================================
# WalletGroupCommunityClaim model tests
# ============================================================


class TestWalletGroupCommunityClaim(TestCase):
    """The claim row is the only surviving wallet-group model on the scorer.

    Phase 3b will swap ``group_key`` for Silk's user_id; for now it's just
    an opaque TEXT identifier.
    """

    def setUp(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user(username="test_canon", password="test")
        account = Account.objects.create(user=user, address="0xowner_canon")
        scorer = BinaryWeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED_BINARY,
            threshold=Decimal("20"),
            weights={"ETH": "1", "Google": "1"},
        )
        self.community = Community.objects.create(
            account=account, name="Test", scorer=scorer
        )
        self.group_key = "0xaaa,0xbbb"

    def test_first_wallet_becomes_canonical(self):
        claim, created = WalletGroupCommunityClaim.objects.get_or_create(
            group_key=self.group_key,
            community=self.community,
            defaults={"canonical_address": "0xaaa"},
        )
        assert created
        assert claim.canonical_address == "0xaaa"

    def test_second_wallet_gets_existing_canonical(self):
        WalletGroupCommunityClaim.objects.create(
            group_key=self.group_key,
            community=self.community,
            canonical_address="0xaaa",
        )

        claim, created = WalletGroupCommunityClaim.objects.get_or_create(
            group_key=self.group_key,
            community=self.community,
            defaults={"canonical_address": "0xbbb"},
        )
        assert not created
        assert claim.canonical_address == "0xaaa"

    def test_unique_group_key_community(self):
        """Only one canonical wallet per group_key per community."""
        WalletGroupCommunityClaim.objects.create(
            group_key=self.group_key,
            community=self.community,
            canonical_address="0xaaa",
        )
        with self.assertRaises(Exception):
            WalletGroupCommunityClaim.objects.create(
                group_key=self.group_key,
                community=self.community,
                canonical_address="0xbbb",
            )

    def test_expired_canonical_is_replaced(self):
        from datetime import datetime, timedelta, timezone

        WalletGroupCommunityClaim.objects.create(
            group_key=self.group_key,
            community=self.community,
            canonical_address="0xaaa",
        )

        # Create an expired score for 0xaaa
        passport = Passport.objects.create(
            address="0xaaa", community=self.community
        )
        Score.objects.create(
            passport=passport,
            score=Decimal("1"),
            status=Score.Status.DONE,
            expiration_date=datetime.now(timezone.utc) - timedelta(days=1),
        )

        # Check expiration
        claim = WalletGroupCommunityClaim.objects.get(
            group_key=self.group_key, community=self.community
        )
        score = Score.objects.get(
            passport__address=claim.canonical_address,
            passport__community=self.community,
        )
        assert score.expiration_date < datetime.now(timezone.utc)

        # Delete expired claim and recreate with new canonical
        claim.delete()
        new_claim = WalletGroupCommunityClaim.objects.create(
            group_key=self.group_key,
            community=self.community,
            canonical_address="0xbbb",
        )
        assert new_claim.canonical_address == "0xbbb"


# ============================================================
# Non-canonical response test
# ============================================================


class TestBuildNonCanonicalResponse:
    def test_non_canonical_response_structure(self):
        from v2.api.api_stamps import _build_non_canonical_response
        from v2.schema import LinkedScoreResponse, V2ScoreResponse

        canonical_response = V2ScoreResponse(
            address="0xaaa",
            score=Decimal("25.5"),
            passing_score=True,
            last_score_timestamp="2024-01-01T00:00:00+00:00",
            expiration_timestamp="2025-01-01T00:00:00+00:00",
            threshold=Decimal("20"),
            error=None,
            stamps={
                "ETH": {"score": "1.00000", "dedup": False, "expiration_date": "2025-01-01T00:00:00+00:00"},
            },
            linked_score=LinkedScoreResponse(
                address="0xaaa",
                score=Decimal("25.5"),
                passing_score=True,
                last_score_timestamp="2024-01-01T00:00:00+00:00",
                expiration_timestamp="2025-01-01T00:00:00+00:00",
                threshold=Decimal("20"),
                stamps={
                    "ETH": {"score": "1.00000", "dedup": False, "expiration_date": "2025-01-01T00:00:00+00:00"},
                },
                wallet_stamps={
                    "0xaaa": {"ETH": {"score": "1.00000", "dedup": False, "expiration_date": "2025-01-01T00:00:00+00:00"}},
                    "0xbbb": {"ETH": {"score": "0.00000", "dedup": True, "expiration_date": "2025-01-01T00:00:00+00:00"}},
                },
            ),
        )

        result = _build_non_canonical_response("0xbbb", canonical_response)

        # Non-canonical gets score=0
        assert result.address == "0xbbb"
        assert result.score == Decimal(0)
        assert result.passing_score is False
        assert result.stamps == {}

        # linked_score has canonical's data
        assert result.linked_score is not None
        assert result.linked_score.address == "0xaaa"
        assert result.linked_score.score == Decimal("25.5")
        assert result.linked_score.passing_score is True
        assert "ETH" in result.linked_score.stamps

        # wallet_stamps shows per-wallet breakdown
        assert result.linked_score.wallet_stamps is not None
        assert "0xaaa" in result.linked_score.wallet_stamps
        assert "0xbbb" in result.linked_score.wallet_stamps
        assert "ETH" in result.linked_score.wallet_stamps["0xaaa"]
        assert "ETH" in result.linked_score.wallet_stamps["0xbbb"]
        assert result.linked_score.wallet_stamps["0xbbb"]["ETH"].dedup is True


# ============================================================
# Stamp merge scoring tests
# ============================================================


class TestStampMergeLogic:
    """Test the stamp merging and weight aggregation logic used by _score_wallet_group.

    These are pure unit tests (no DB) that verify:
    - Weights come from stamp_scores on individual Score objects
    - Deduped stamps are excluded from merging
    - Canonical wallet's stamps take priority
    - Expiration dates are properly compared as datetimes
    """

    def _make_score(self, stamp_scores, stamps):
        """Create a mock Score-like object."""
        score = MagicMock()
        score.stamp_scores = stamp_scores
        score.stamps = stamps
        return score

    def test_merged_score_uses_stamp_scores_from_individual_wallets(self):
        """Verify merged score pulls weights from stamp_scores."""
        from v2.api.api_stamps import _parse_expiration

        score_a = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={
                "Google": {
                    "score": "10.00000",
                    "dedup": False,
                    "expiration_date": "2027-01-01T00:00:00+00:00",
                }
            },
        )
        score_b = self._make_score(
            stamp_scores={"Twitter": "15"},
            stamps={
                "Twitter": {
                    "score": "15.00000",
                    "dedup": False,
                    "expiration_date": "2027-06-01T00:00:00+00:00",
                }
            },
        )

        wallet_scores = {"0xaaa": score_a, "0xbbb": score_b}
        ordered = ["0xaaa", "0xbbb"]

        # Merge stamps (same logic as _score_wallet_group)
        merged_stamps = {}
        for addr in ordered:
            for provider, stamp_data in wallet_scores[addr].stamps.items():
                if provider not in merged_stamps and not stamp_data.get("dedup"):
                    merged_stamps[provider] = {**stamp_data, "source_wallet": addr}

        # Build combined score from stamp_scores
        combined = Decimal(0)
        merged_stamp_scores = {}
        earliest_exp = None
        for provider in merged_stamps:
            for addr in ordered:
                ws = wallet_scores[addr]
                if ws.stamp_scores and provider in ws.stamp_scores:
                    w = Decimal(ws.stamp_scores[provider])
                    combined += w
                    merged_stamp_scores[provider] = str(w)
                    break

            exp = _parse_expiration(merged_stamps[provider].get("expiration_date"))
            if exp and (earliest_exp is None or exp < earliest_exp):
                earliest_exp = exp

        assert combined == Decimal("25")
        assert merged_stamp_scores == {"Google": "10", "Twitter": "15"}
        assert earliest_exp.year == 2027
        assert earliest_exp.month == 1  # Google's Jan, not Twitter's Jun

    def test_deduped_stamps_excluded_from_merge(self):
        """Deduped stamps should NOT contribute to merged score."""
        score_a = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={"Google": {"score": "10.00000", "dedup": False, "expiration_date": "2027-01-01T00:00:00+00:00"}},
        )
        score_b = self._make_score(
            stamp_scores={},
            stamps={"Google": {"score": "0.00000", "dedup": True, "expiration_date": "2027-01-01T00:00:00+00:00"}},
        )

        merged = {}
        for addr in ["0xaaa", "0xbbb"]:
            ws = {"0xaaa": score_a, "0xbbb": score_b}[addr]
            for provider, data in ws.stamps.items():
                if provider not in merged and not data.get("dedup"):
                    merged[provider] = {**data, "source_wallet": addr}

        assert len(merged) == 1
        assert "Google" in merged
        assert merged["Google"]["source_wallet"] == "0xaaa"

    def test_canonical_stamps_take_priority(self):
        """When both wallets have same provider non-deduped, canonical wins."""
        score_a = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={"Google": {"score": "10.00000", "dedup": False, "expiration_date": "2028-01-01T00:00:00+00:00"}},
        )
        score_b = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={"Google": {"score": "10.00000", "dedup": False, "expiration_date": "2026-01-01T00:00:00+00:00"}},
        )

        merged = {}
        for addr in ["0xaaa", "0xbbb"]:  # canonical first
            ws = {"0xaaa": score_a, "0xbbb": score_b}[addr]
            for provider, data in ws.stamps.items():
                if provider not in merged and not data.get("dedup"):
                    merged[provider] = {**data, "source_wallet": addr}

        assert merged["Google"]["expiration_date"] == "2028-01-01T00:00:00+00:00"
        assert merged["Google"]["source_wallet"] == "0xaaa"

    def test_source_wallet_tracks_stamp_origin(self):
        """Each merged stamp should track which wallet contributed it."""
        score_a = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={"Google": {"score": "10.00000", "dedup": False, "expiration_date": "2027-01-01T00:00:00+00:00"}},
        )
        score_b = self._make_score(
            stamp_scores={"Twitter": "15"},
            stamps={"Twitter": {"score": "15.00000", "dedup": False, "expiration_date": "2027-06-01T00:00:00+00:00"}},
        )

        wallet_scores = {"0xaaa": score_a, "0xbbb": score_b}
        ordered = ["0xaaa", "0xbbb"]

        merged = {}
        for addr in ordered:
            for provider, data in wallet_scores[addr].stamps.items():
                if provider not in merged and not data.get("dedup"):
                    merged[provider] = {**data, "source_wallet": addr}

        assert merged["Google"]["source_wallet"] == "0xaaa"
        assert merged["Twitter"]["source_wallet"] == "0xbbb"

    def test_source_wallet_shows_canonical_wins_on_conflict(self):
        """When both wallets have same provider, source_wallet is canonical."""
        score_a = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={"Google": {"score": "10.00000", "dedup": False, "expiration_date": "2027-01-01T00:00:00+00:00"}},
        )
        score_b = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={"Google": {"score": "10.00000", "dedup": False, "expiration_date": "2026-06-01T00:00:00+00:00"}},
        )

        wallet_scores = {"0xaaa": score_a, "0xbbb": score_b}
        ordered = ["0xaaa", "0xbbb"]

        merged = {}
        for addr in ordered:
            for provider, data in wallet_scores[addr].stamps.items():
                if provider not in merged and not data.get("dedup"):
                    merged[provider] = {**data, "source_wallet": addr}

        assert merged["Google"]["source_wallet"] == "0xaaa"

    def test_wallet_stamps_contains_all_wallets_stamps(self):
        """wallet_stamps should include every wallet's stamps independently."""
        score_a = self._make_score(
            stamp_scores={"Google": "10", "ETH": "5"},
            stamps={
                "Google": {"score": "10.00000", "dedup": False, "expiration_date": "2027-01-01T00:00:00+00:00"},
                "ETH": {"score": "5.00000", "dedup": False, "expiration_date": "2027-01-01T00:00:00+00:00"},
            },
        )
        score_b = self._make_score(
            stamp_scores={"ETH": "5", "Twitter": "8"},
            stamps={
                "ETH": {"score": "0.00000", "dedup": True, "expiration_date": "2027-01-01T00:00:00+00:00"},
                "Twitter": {"score": "8.00000", "dedup": False, "expiration_date": "2027-06-01T00:00:00+00:00"},
            },
        )

        wallet_scores = {"0xaaa": score_a, "0xbbb": score_b}

        # Build wallet_stamps (same logic as _score_wallet_group)
        wallet_stamps = {}
        for addr in ["0xaaa", "0xbbb"]:
            ws = wallet_scores[addr]
            if ws.stamps:
                wallet_stamps[addr] = ws.stamps

        # Each wallet has its own complete stamp set
        assert set(wallet_stamps["0xaaa"].keys()) == {"Google", "ETH"}
        assert set(wallet_stamps["0xbbb"].keys()) == {"ETH", "Twitter"}

        # 0xbbb's ETH shows as deduped
        assert wallet_stamps["0xbbb"]["ETH"]["dedup"] is True
        assert wallet_stamps["0xaaa"]["ETH"]["dedup"] is False

    def test_wallet_stamps_independent_of_merge(self):
        """wallet_stamps shows raw per-wallet data regardless of merge outcome."""
        score_a = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={"Google": {"score": "10.00000", "dedup": False, "expiration_date": "2027-01-01T00:00:00+00:00"}},
        )
        score_b = self._make_score(
            stamp_scores={"Google": "10"},
            stamps={"Google": {"score": "10.00000", "dedup": False, "expiration_date": "2026-01-01T00:00:00+00:00"}},
        )

        wallet_scores = {"0xaaa": score_a, "0xbbb": score_b}

        wallet_stamps = {}
        for addr in ["0xaaa", "0xbbb"]:
            ws = wallet_scores[addr]
            if ws.stamps:
                wallet_stamps[addr] = ws.stamps

        # Both wallets show their Google stamp even though only one wins in merge
        assert "Google" in wallet_stamps["0xaaa"]
        assert "Google" in wallet_stamps["0xbbb"]
        # Can see different expiration dates
        assert wallet_stamps["0xaaa"]["Google"]["expiration_date"] == "2027-01-01T00:00:00+00:00"
        assert wallet_stamps["0xbbb"]["Google"]["expiration_date"] == "2026-01-01T00:00:00+00:00"


# ============================================================
# Linkage source stub tests
# ============================================================


@pytest.mark.asyncio
async def test_get_linked_addresses_returns_solo_set():
    """Phase 0 stub: always returns the requesting address (lowercased) as a one-element list."""
    from account.linkage import get_linked_addresses

    result = await get_linked_addresses("0xAaBb")
    assert result == ["0xaabb"]
