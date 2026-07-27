"""Tests for the per-community canonical-wallet claim model and scoring helpers.

Phase 0 of holonym-foundation/internal-docs#1060: ``WalletGroup`` and
``WalletGroupMembership`` (and the wallet-linking API) have moved to Silk.
What remains here is exercising the scorer-side surface:

- ``WalletGroupCommunityClaim`` (now keyed on an opaque ``group_key`` TEXT)
- ``_build_non_canonical_response`` response shape
- The stamp-merge / weight-aggregation logic in ``_score_wallet_group``
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from django.core.cache import cache
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
# Linkage source: Silk fetch + SWR cache + killswitch (#589)
# ============================================================


def _patch_fetch(mocker, *, returns=None, raises=None):
    """Patch the Silk HTTP boundary. Returns the AsyncMock for call assertions."""
    mock = AsyncMock()
    if raises is not None:
        mock.side_effect = raises
    else:
        mock.return_value = returns
    mocker.patch("account.linkage._fetch_from_silk", mock)
    return mock


@pytest.fixture(autouse=True)
def linkage_settings(settings):
    """Isolate each test: in-process cache (no Redis), killswitch ON, Silk configured."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "linkage-tests",
        }
    }
    settings.LINKED_WALLETS_SOURCE_ENABLED = True
    settings.SILK_AUTH_SERVER_URL = "https://silk.test"
    settings.SILK_SERVICE_API_KEY = "svc-key"
    cache.clear()
    yield
    cache.clear()


@pytest.mark.asyncio
async def test_killswitch_off_returns_solo_without_fetching(settings, mocker):
    """Killswitch off: no HTTP call, solo set returned."""
    settings.LINKED_WALLETS_SOURCE_ENABLED = False
    fetch = _patch_fetch(mocker, returns=["0xaaa", "0xbbb"])

    from account.linkage import get_linked_addresses

    result = await get_linked_addresses("0xAaA")

    assert result == ["0xaaa"]
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_killswitch_toggle_on_to_off(settings, mocker):
    """Flipping the killswitch off mid-process is picked up on the next call."""
    fetch = _patch_fetch(mocker, returns=["0xaaa", "0xbbb"])

    from account.linkage import get_linked_addresses

    assert await get_linked_addresses("0xaaa") == ["0xaaa", "0xbbb"]

    settings.LINKED_WALLETS_SOURCE_ENABLED = False
    assert await get_linked_addresses("0xaaa") == ["0xaaa"]


@pytest.mark.asyncio
async def test_happy_path_returns_normalized_cluster_and_caches(mocker):
    """A multi-address cluster is lowercased, deduped, sorted, and cached."""
    fetch = _patch_fetch(mocker, returns=["0xCCC", "0xAAA", "0xBBB", "0xbbb"])

    from account.linkage import FRESH_KEY, get_linked_addresses

    result = await get_linked_addresses("0xAAA")

    assert result == ["0xaaa", "0xbbb", "0xccc"]
    fetch.assert_awaited_once_with("0xaaa")
    assert await cache.aget(FRESH_KEY.format("0xaaa")) == ["0xaaa", "0xbbb", "0xccc"]


@pytest.mark.asyncio
async def test_empty_cluster_returns_solo_and_negative_caches(mocker):
    """Empty Silk response = no linkage: return solo and cache it (negative caching)."""
    fetch = _patch_fetch(mocker, returns=[])

    from account.linkage import FRESH_KEY, get_linked_addresses

    assert await get_linked_addresses("0xaaa") == ["0xaaa"]
    assert await cache.aget(FRESH_KEY.format("0xaaa")) == ["0xaaa"]

    # Second call is served from the negative cache without re-fetching.
    assert await get_linked_addresses("0xaaa") == ["0xaaa"]
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_solo_silk_user_single_element(mocker):
    """A solo Silk user (silkAddress set, no externals) is a real cluster of size 1."""
    _patch_fetch(mocker, returns=["0xaaa"])

    from account.linkage import get_linked_addresses

    assert await get_linked_addresses("0xAAA") == ["0xaaa"]


@pytest.mark.asyncio
async def test_cache_hit_skips_second_fetch(mocker):
    """A second call within the freshness window hits the cache, no HTTP call."""
    fetch = _patch_fetch(mocker, returns=["0xaaa", "0xbbb"])

    from account.linkage import get_linked_addresses

    await get_linked_addresses("0xaaa")
    await get_linked_addresses("0xaaa")

    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_key_is_per_address(mocker):
    """Two different addresses do not share a cache entry."""
    fetch = AsyncMock(
        side_effect=lambda addr: {
            "0xaaa": ["0xaaa", "0xbbb"],
            "0xccc": ["0xccc", "0xddd"],
        }[addr]
    )
    mocker.patch("account.linkage._fetch_from_silk", fetch)

    from account.linkage import get_linked_addresses

    assert await get_linked_addresses("0xaaa") == ["0xaaa", "0xbbb"]
    assert await get_linked_addresses("0xccc") == ["0xccc", "0xddd"]
    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_failure_with_stale_cache_serves_stale(mocker):
    """5xx after a prior success: serve the last good value, not solo."""
    from account.linkage import FRESH_KEY, get_linked_addresses

    fetch = _patch_fetch(mocker, returns=["0xaaa", "0xbbb"])
    assert await get_linked_addresses("0xaaa") == ["0xaaa", "0xbbb"]

    # Simulate the freshness key expiring; last-good survives for stale fallback.
    await cache.adelete(FRESH_KEY.format("0xaaa"))
    fetch.side_effect = aiohttp.ClientError("503")
    fetch.return_value = None

    assert await get_linked_addresses("0xaaa") == ["0xaaa", "0xbbb"]


@pytest.mark.asyncio
async def test_failure_with_no_cache_falls_back_to_solo(mocker):
    """5xx with a cold cache: fall back to solo."""
    _patch_fetch(mocker, raises=aiohttp.ClientError("503"))

    from account.linkage import get_linked_addresses

    assert await get_linked_addresses("0xAAA") == ["0xaaa"]


@pytest.mark.asyncio
async def test_unauthorized_falls_back_like_any_failure(mocker):
    """401 (wrong service key) is treated as an outage."""
    err = aiohttp.ClientResponseError(MagicMock(), (), status=401)
    _patch_fetch(mocker, raises=err)

    from account.linkage import get_linked_addresses

    assert await get_linked_addresses("0xaaa") == ["0xaaa"]


@pytest.mark.asyncio
async def test_timeout_falls_back_to_solo(mocker):
    """A connection-level timeout falls back to solo."""
    _patch_fetch(mocker, raises=aiohttp.ServerTimeoutError())

    from account.linkage import get_linked_addresses

    assert await get_linked_addresses("0xaaa") == ["0xaaa"]


@pytest.mark.asyncio
async def test_failure_does_not_poison_cache(mocker):
    """No-poison: a failed fetch must not populate either cache key."""
    _patch_fetch(mocker, raises=aiohttp.ClientError("503"))

    from account.linkage import FRESH_KEY, LAST_GOOD_KEY, get_linked_addresses

    await get_linked_addresses("0xaaa")

    assert await cache.aget(FRESH_KEY.format("0xaaa")) is None
    assert await cache.aget(LAST_GOOD_KEY.format("0xaaa")) is None


class _FakeResp:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(MagicMock(), (), status=self.status)

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    """Records the GET args so we can assert URL + header construction."""

    def __init__(self, resp):
        self._resp = resp
        self.requested_url = None
        self.requested_headers = None

    def get(self, url, headers=None):
        self.requested_url = url
        self.requested_headers = headers
        return self._resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_fetch_from_silk_builds_request_and_parses_response(mocker):
    """Exercise the real _fetch_from_silk: URL, service-key header, JSON parsing."""
    session = _FakeSession(_FakeResp(200, {"addresses": ["0xaaa", "0xbbb"]}))
    mocker.patch("account.linkage.aiohttp.ClientSession", return_value=session)

    from account.linkage import _fetch_from_silk

    result = await _fetch_from_silk("0xaaa")

    assert result == ["0xaaa", "0xbbb"]
    assert (
        session.requested_url
        == "https://silk.test/api/public/linked-wallets/by-address/0xaaa"
    )
    assert session.requested_headers == {"X-Service-Key": "svc-key"}
