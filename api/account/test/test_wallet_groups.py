"""Tests for wallet group models, linking API, and scoring integration."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
from django.test import TestCase, override_settings

from account.models import (
    Account,
    Community,
    WalletGroup,
    WalletGroupCommunityClaim,
    WalletGroupMembership,
)
from registry.models import Passport, Score
from scorer_weighted.models import BinaryWeightedScorer, Scorer


@pytest.fixture
def wallet_group(db):
    """Create a wallet group with two members."""
    group = WalletGroup.objects.create()
    WalletGroupMembership.objects.create(group=group, address="0xaaa")
    WalletGroupMembership.objects.create(group=group, address="0xbbb")
    return group


@pytest.fixture
def community(db):
    """Create a test community with a binary weighted scorer."""
    from django.contrib.auth.models import User

    user = User.objects.create_user(username="testuser", password="testpass")
    account = Account.objects.create(user=user, address="0xowner")
    scorer = BinaryWeightedScorer.objects.create(
        type=Scorer.Type.WEIGHTED_BINARY,
        threshold=Decimal("20"),
    )
    community = Community.objects.create(
        account=account,
        name="Test Community",
        scorer=scorer,
    )
    return community


# ============================================================
# Model tests
# ============================================================


class TestWalletGroupModels(TestCase):
    def test_create_wallet_group(self):
        group = WalletGroup.objects.create()
        self.assertIsNotNone(group.id)
        self.assertIsNotNone(group.created_at)

    def test_create_membership(self):
        group = WalletGroup.objects.create()
        m = WalletGroupMembership.objects.create(
            group=group, address="0xaaa"
        )
        self.assertEqual(m.address, "0xaaa")
        self.assertEqual(m.group, group)

    def test_unique_address_constraint(self):
        """Each address can only be in one group."""
        group1 = WalletGroup.objects.create()
        group2 = WalletGroup.objects.create()
        WalletGroupMembership.objects.create(group=group1, address="0xaaa")
        with self.assertRaises(Exception):
            WalletGroupMembership.objects.create(
                group=group2, address="0xaaa"
            )

    def test_unique_community_claim(self):
        """Only one canonical wallet per group per community."""
        from django.contrib.auth.models import User

        user = User.objects.create_user(username="test", password="test")
        account = Account.objects.create(user=user, address="0xowner")
        scorer = BinaryWeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED_BINARY,
            threshold=Decimal("20"),
            weights={"ETH": "1", "Google": "1"},
        )
        community = Community.objects.create(
            account=account, name="Test", scorer=scorer
        )
        group = WalletGroup.objects.create()

        WalletGroupCommunityClaim.objects.create(
            group=group, community=community, canonical_address="0xaaa"
        )
        with self.assertRaises(Exception):
            WalletGroupCommunityClaim.objects.create(
                group=group, community=community, canonical_address="0xbbb"
            )

    def test_cascade_delete_group(self):
        """Deleting a group cascades to memberships and claims."""
        group = WalletGroup.objects.create()
        WalletGroupMembership.objects.create(group=group, address="0xaaa")
        group.delete()
        self.assertEqual(WalletGroupMembership.objects.count(), 0)


# ============================================================
# Scoring helper tests
# ============================================================


class TestGetWalletGroup(TestCase):
    def test_no_group(self):
        """Address not in a group returns None."""
        result = WalletGroupMembership.objects.filter(address="0xnogroup").first()
        assert result is None

    def test_with_group(self):
        """Address in a group returns all group members."""
        group = WalletGroup.objects.create()
        WalletGroupMembership.objects.create(group=group, address="0xaaa")
        WalletGroupMembership.objects.create(group=group, address="0xbbb")

        membership = WalletGroupMembership.objects.get(address="0xaaa")
        addresses = list(
            WalletGroupMembership.objects.filter(
                group_id=membership.group_id
            ).values_list("address", flat=True)
        )
        assert set(addresses) == {"0xaaa", "0xbbb"}


class TestCanonicalClaim(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.group = WalletGroup.objects.create()
        WalletGroupMembership.objects.create(group=self.group, address="0xaaa")
        WalletGroupMembership.objects.create(group=self.group, address="0xbbb")

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

    def test_first_wallet_becomes_canonical(self):
        claim, created = WalletGroupCommunityClaim.objects.get_or_create(
            group=self.group,
            community=self.community,
            defaults={"canonical_address": "0xaaa"},
        )
        assert created
        assert claim.canonical_address == "0xaaa"

    def test_second_wallet_gets_existing_canonical(self):
        WalletGroupCommunityClaim.objects.create(
            group=self.group,
            community=self.community,
            canonical_address="0xaaa",
        )

        claim, created = WalletGroupCommunityClaim.objects.get_or_create(
            group=self.group,
            community=self.community,
            defaults={"canonical_address": "0xbbb"},
        )
        assert not created
        assert claim.canonical_address == "0xaaa"

    def test_expired_canonical_is_replaced(self):
        from datetime import datetime, timezone, timedelta

        WalletGroupCommunityClaim.objects.create(
            group=self.group,
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
            group=self.group, community=self.community
        )
        score = Score.objects.get(
            passport__address=claim.canonical_address,
            passport__community=self.community,
        )
        assert score.expiration_date < datetime.now(timezone.utc)

        # Delete expired claim and recreate with new canonical
        claim.delete()
        new_claim = WalletGroupCommunityClaim.objects.create(
            group=self.group,
            community=self.community,
            canonical_address="0xbbb",
        )
        assert new_claim.canonical_address == "0xbbb"


# ============================================================
# Non-canonical response test
# ============================================================


@pytest.mark.django_db
class TestBuildNonCanonicalResponse:
    def test_non_canonical_response_structure(self):
        from v2.api.api_stamps import _build_non_canonical_response
        from v2.schema import V2ScoreResponse

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


# ============================================================
# Wallet group API tests (with mocked SIWE)
# ============================================================


@pytest.mark.django_db
class TestWalletGroupAPI:
    """Test the wallet group API endpoints with mocked SIWE verification."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from django.test import Client

        self.client = Client()

    def _mock_siwe(self, address):
        """Create a mock SIWE payload that will verify as the given address."""
        return {
            "message": {
                "address": address,
                "nonce": "test_nonce",
                "domain": "localhost",
                "version": "1",
                "chainId": 1,
                "uri": "http://localhost",
                "issuedAt": "2024-01-01T00:00:00Z",
            },
            "signature": "0xfake",
        }

    @patch(
        "account.api_wallet_groups.verify_siwe_ownership",
        side_effect=lambda p: p.message["address"].lower(),
    )
    def test_link_wallets(self, mock_verify):
        import json

        response = self.client.post(
            "/account/wallet-groups/link",
            data=json.dumps(
                {
                    "wallet_a": self._mock_siwe("0xAAA"),
                    "wallet_b": self._mock_siwe("0xBBB"),
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "group_id" in data
        assert set(data["addresses"]) == {"0xaaa", "0xbbb"}

    @patch(
        "account.api_wallet_groups.verify_siwe_ownership",
        side_effect=lambda p: p.message["address"].lower(),
    )
    def test_link_duplicate_wallet(self, mock_verify):
        """Can't link a wallet that's already in a group."""
        import json

        # First link
        self.client.post(
            "/account/wallet-groups/link",
            data=json.dumps(
                {
                    "wallet_a": self._mock_siwe("0xAAA"),
                    "wallet_b": self._mock_siwe("0xBBB"),
                }
            ),
            content_type="application/json",
        )

        # Try to link 0xAAA again
        response = self.client.post(
            "/account/wallet-groups/link",
            data=json.dumps(
                {
                    "wallet_a": self._mock_siwe("0xAAA"),
                    "wallet_b": self._mock_siwe("0xCCC"),
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 400

    @patch(
        "account.api_wallet_groups.verify_siwe_ownership",
        side_effect=lambda p: p.message["address"].lower(),
    )
    def test_add_wallet_to_group(self, mock_verify):
        import json

        # Create initial group
        resp = self.client.post(
            "/account/wallet-groups/link",
            data=json.dumps(
                {
                    "wallet_a": self._mock_siwe("0xAAA"),
                    "wallet_b": self._mock_siwe("0xBBB"),
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200

        # Add third wallet
        response = self.client.post(
            "/account/wallet-groups/add",
            data=json.dumps(
                {
                    "existing_member": self._mock_siwe("0xAAA"),
                    "new_wallet": self._mock_siwe("0xCCC"),
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["addresses"]) == 3
        assert "0xccc" in data["addresses"]

    @patch(
        "account.api_wallet_groups.verify_siwe_ownership",
        side_effect=lambda p: p.message["address"].lower(),
    )
    def test_unlink_wallet(self, mock_verify):
        import json

        # Create group
        self.client.post(
            "/account/wallet-groups/link",
            data=json.dumps(
                {
                    "wallet_a": self._mock_siwe("0xAAA"),
                    "wallet_b": self._mock_siwe("0xBBB"),
                }
            ),
            content_type="application/json",
        )

        # Add third so unlinking doesn't destroy group
        self.client.post(
            "/account/wallet-groups/add",
            data=json.dumps(
                {
                    "existing_member": self._mock_siwe("0xAAA"),
                    "new_wallet": self._mock_siwe("0xCCC"),
                }
            ),
            content_type="application/json",
        )

        # Unlink 0xBBB
        response = self.client.post(
            "/account/wallet-groups/unlink",
            data=json.dumps(self._mock_siwe("0xBBB")),
            content_type="application/json",
        )
        assert response.status_code == 200

        # Verify 0xBBB is no longer in the group
        assert not WalletGroupMembership.objects.filter(
            address="0xbbb"
        ).exists()

    @patch(
        "account.api_wallet_groups.verify_siwe_ownership",
        side_effect=lambda p: p.message["address"].lower(),
    )
    def test_unlink_last_two_destroys_group(self, mock_verify):
        import json

        # Create group of 2
        resp = self.client.post(
            "/account/wallet-groups/link",
            data=json.dumps(
                {
                    "wallet_a": self._mock_siwe("0xAAA"),
                    "wallet_b": self._mock_siwe("0xBBB"),
                }
            ),
            content_type="application/json",
        )
        group_id = resp.json()["group_id"]

        # Unlink one - group should be destroyed
        self.client.post(
            "/account/wallet-groups/unlink",
            data=json.dumps(self._mock_siwe("0xBBB")),
            content_type="application/json",
        )

        assert not WalletGroup.objects.filter(id=group_id).exists()
        assert not WalletGroupMembership.objects.filter(
            address="0xaaa"
        ).exists()

    def test_get_wallet_group(self):
        group = WalletGroup.objects.create()
        WalletGroupMembership.objects.create(group=group, address="0xaaa")
        WalletGroupMembership.objects.create(group=group, address="0xbbb")

        response = self.client.get("/account/wallet-groups/0xAAA")
        assert response.status_code == 200
        data = response.json()
        assert data["group_id"] == group.id
        assert set(data["addresses"]) == {"0xaaa", "0xbbb"}

    def test_get_wallet_group_not_found(self):
        response = self.client.get("/account/wallet-groups/0xNotInGroup")
        assert response.status_code == 404
