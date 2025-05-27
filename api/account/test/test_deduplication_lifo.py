from datetime import datetime
from unittest import mock

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from ninja_jwt.schema import RefreshToken

from account.deduplication import Rules
from account.deduplication.lifo import HashScorerLinkIntegrityError, alifo
from account.models import Account, Community
from registry.models import Event, HashScorerLink
from scorer_weighted.models import Scorer, WeightedScorer

User = get_user_model()

mock_community_body = {"name": "test", "description": "test"}


credential_with_hash = {
    "credential": {
        "credentialSubject": {
            "hash": "v1:test_hash",
            "provider": "test_provider",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}

credential_with_1_nullifier = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v1:test_hash"],
            "provider": "test_provider",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}

credential_with_2_nullifiers = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v1:test_hash", "v2:test_hash"],
            "provider": "test_provider",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}


class LifoDeduplicationWith1NullifierTestCase(TransactionTestCase):
    def setUp(self):
        self.credential = credential_with_1_nullifier
        cs = self.credential["credential"]["credentialSubject"]
        self.expect_nullifiers = (
            cs["nullifiers"] if "nullifiers" in cs else [cs["hash"]]
        )
        self.expect_expiration_date = datetime.fromisoformat(
            self.credential["credential"]["expirationDate"]
        )

        User.objects.create_user(username="admin", password="12345")

        self.user = User.objects.create_user(username="testuser-1", password="12345")
        self.user2 = User.objects.create_user(username="testuser-2", password="12345")

        refresh = RefreshToken.for_user(self.user)
        refresh["ip_address"] = "127.0.0.1"
        self.access_token = refresh.access_token

        (self.account1, _) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )
        scorer1 = WeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED, weights={"test_provider": 10}
        )
        self.community1 = Community.objects.create(
            name="Community1", scorer=scorer1, rule=Rules.LIFO, account=self.account1
        )

        (self.account2, _) = Account.objects.get_or_create(
            user=self.user2, defaults={"address": "0x0"}
        )
        scorer2 = WeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED, weights={"test_provider": 10}
        )
        self.community2 = Community.objects.create(
            name="Community2", scorer=scorer2, rule=Rules.LIFO, account=self.account2
        )

    @async_to_sync
    async def test_lifo_no_deduplicate_across_cummunities(self):
        """
        Test that the deduplication method is not deduplicating stamps across communities.
        This means the user can submit the same stamps to different communities, and they will not
        be discarded by the `lifo` deduplication method
        """

        # Step 1/2: run dedupe stamp in community 1
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [self.credential]},
            "0xaddress_1",
        )
        # We expect the passport not to be deduped, as the duplicate hash is
        # contained in a different community
        self.assertDictEqual(deduped_passport, {"stamps": [self.credential]})
        self.assertDictEqual(clashing_stamps, {})

        # Check for the hash links
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links,
            [
                (nullifier, self.expect_expiration_date)
                for nullifier in self.expect_nullifiers
            ],
        )

        # Step 2/2: run dedupe stamp in community 2 with another address, expect no deduplication
        deduped_passport, _, clashing_stamps = await alifo(
            self.community2,
            {"stamps": [self.credential]},
            "0xaddress_2",
        )
        # We expect the passport not to be deduped, as the duplicate hash is
        # contained in a different community
        self.assertDictEqual(deduped_passport, {"stamps": [self.credential]})
        self.assertDictEqual(clashing_stamps, {})

        # Check for the hash links for address_2 and community2
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_2", community=self.community2
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links,
            [
                (nullifier, self.expect_expiration_date)
                for nullifier in self.expect_nullifiers
            ],
        )

    @async_to_sync
    async def test_lifo_no_deduplicate_same_passport_address_across_cummunities(self):
        """
        Test that the deduplication method is not deduplicating stamps owned by the
        same address across communities.
        This means the user can submit the same stamps to different communities with the
        same ETH address, and they will not be discarded by the `lifo` deduplication method
        """

        # Step 1/2: run dedupe stamp in community 1
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [self.credential]},
            "0xaddress_1",
        )
        # We expect the passport not to be deduped, as the duplicate hash is
        # contained in a different community
        self.assertDictEqual(deduped_passport, {"stamps": [self.credential]})
        self.assertDictEqual(clashing_stamps, {})

        # Check for the hash links
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links,
            [
                (nullifier, self.expect_expiration_date)
                for nullifier in self.expect_nullifiers
            ],
        )

        # Step 2/2: run dedupe stamp in community 2 with same address, expect no deduplication
        deduped_passport, _, clashing_stamps = await alifo(
            self.community2,
            {"stamps": [self.credential]},
            "0xaddress_1",
        )
        # We expect the passport not to be deduped, as the duplicate hash is
        # contained in a different community
        self.assertDictEqual(deduped_passport, {"stamps": [self.credential]})
        self.assertDictEqual(clashing_stamps, {})

        # Check for the hash links
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community2
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links,
            [
                (nullifier, self.expect_expiration_date)
                for nullifier in self.expect_nullifiers
            ],
        )

    @async_to_sync
    async def test_lifo_deduplicate(self):
        """
        Verifies that deduplication works if the user submits the same stamps to a community
        but as part of different passports
        """

        # Step 1/2: run dedupe stamp in community 1
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [self.credential]},
            "0xaddress_1",
        )

        # We expect the passport to not be deduped, as it is the same owner
        self.assertDictEqual(deduped_passport, {"stamps": [self.credential]})
        self.assertDictEqual(clashing_stamps, {})

        # Check for the hash links
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links,
            [
                (nullifier, self.expect_expiration_date)
                for nullifier in self.expect_nullifiers
            ],
        )

        # Step 2/2: run dedupe stamp in community 1 with another address, expect deduplication
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1, {"stamps": [self.credential]}, "0xaddress_2"
        )

        # We expect the passport to be deduped, and the return copy shall contain
        # no stamps
        self.assertDictEqual(deduped_passport, {"stamps": []})
        self.assertDictEqual(
            clashing_stamps,
            {
                "test_provider": self.credential,
            },
        )
        # Check for the hash links
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_2", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links,
            [],
        )

    def test_retry_on_clash(self):
        """
        This tests functionality that causes the deduplication method to retry
        when there is a collision with another deduplication happening at the
        same time. It's not possible to test this directly, so instead we're
        sending in a payload with two stamps with the same credential, which
        wouldn't make it past the previous validation step in the real flow.
        """

        call_count = 0

        def increment_call_count(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return HashScorerLink.objects.none()

        with mock.patch(
            "account.deduplication.lifo.HashScorerLink.objects.filter",
            side_effect=increment_call_count,
        ):
            with self.assertRaises(HashScorerLinkIntegrityError):
                async_to_sync(alifo)(
                    self.community1,
                    {
                        "stamps": [
                            self.credential,
                            self.credential,
                        ]
                    },
                    "0xaddress_1",
                )
        self.assertEqual(call_count, 5)

    async def test_dedupe_events(self):
        """
        Check that the expected deduplication events are created
        """
        # Step 1/2: run dedupe stamp in community 1
        _, _, _ = await alifo(
            self.community1,
            {"stamps": [self.credential]},
            "0xaddress_1",
        )

        events = [
            e
            async for e in Event.objects.filter(
                community=self.community1, action=Event.Action.LIFO_DEDUPLICATION
            ).values_list("address", "data")
        ]
        self.assertListEqual(events, [])

        # Step 2/2: run dedupe stamp in community 1 on address 2
        _, _, _ = await alifo(
            self.community1,
            {"stamps": [self.credential]},
            "0xaddress_2",
        )
        events = [
            e
            async for e in Event.objects.filter(
                community=self.community1, action=Event.Action.LIFO_DEDUPLICATION
            ).values_list("address", "data")
        ]
        self.assertListEqual(
            events,
            [
                (
                    "0xaddress_2",
                    {
                        "nullifiers": self.expect_nullifiers,
                        "provider": self.credential["credential"]["credentialSubject"][
                            "provider"
                        ],
                        "community_id": self.community1.pk,
                    },
                )
            ],
        )

    @async_to_sync
    async def test_backfill_duplicate_processing_bug(self):
        """
        Test for the backfill logic fix. Even though we can't reproduce the original bug
        in the test environment, this test verifies that the backfill logic properly
        handles existing hash links.
        """

        # Step 1: User A submits stamp with only hash-A
        credential_a = {
            "credential": {
                "credentialSubject": {
                    "nullifiers": ["hash-A"],  # only 1 nullifier
                    "provider": "test_provider",
                },
                "expirationDate": "2099-02-21T15:30:51.720Z",
            },
        }

        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_a]},
            "0xaddress_1",
        )

        # Should not be deduplicated (first submission)
        self.assertEqual(len(deduped_passport["stamps"]), 1)
        self.assertEqual(clashing_stamps, {})

        # Step 2: User B submits stamp with ["hash-A", "hash-B"]
        # This should clash on hash-A and backfill hash-B for User A
        credential_ab = {
            "credential": {
                "credentialSubject": {
                    "nullifiers": ["hash-A", "hash-B"],  # 2 nullifiers
                    "provider": "test_provider",
                },
                "expirationDate": "2099-02-21T15:30:51.720Z",
            },
        }

        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_ab]},
            "0xaddress_2",
        )

        # Should be deduplicated due to hash-A clash
        self.assertEqual(len(deduped_passport["stamps"]), 0)
        self.assertEqual(clashing_stamps, {"test_provider": credential_ab})

        # Step 3: User B submits the SAME stamp again
        # This should work without errors (the fix ensures no duplicate creation)
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_ab]},
            "0xaddress_2",
        )

        # Should still be deduplicated
        self.assertEqual(len(deduped_passport["stamps"]), 0)
        self.assertEqual(clashing_stamps, {"test_provider": credential_ab})

        # Verify hash links are correct (no duplicates)
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community1
            )
            .values_list("hash", "address")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links, [("hash-A", "0xaddress_1"), ("hash-B", "0xaddress_1")]
        )


class LifoDeduplicationWith2NullifiersTestCase(LifoDeduplicationWith1NullifierTestCase):
    """
    Repeat the same tests for stamps with 2 nullifiers
    """

    def setUp(self):
        super().setUp()
        self.credential = credential_with_2_nullifiers

        # Override input credential and expected values
        self.credential = credential_with_hash
        cs = self.credential["credential"]["credentialSubject"]
        self.expect_nullifiers = (
            cs["nullifiers"] if "nullifiers" in cs else [cs["hash"]]
        )
        self.expect_expiration_date = datetime.fromisoformat(
            self.credential["credential"]["expirationDate"]
        )


class LifoDeduplicationWithHashTestCase(LifoDeduplicationWith1NullifierTestCase):
    """
    Repeat the same tests for stamps with the hash field
    """

    def setUp(self):
        super().setUp()

        # Override input credential and expected values
        self.credential = credential_with_hash
        cs = self.credential["credential"]["credentialSubject"]
        self.expect_nullifiers = (
            cs["nullifiers"] if "nullifiers" in cs else [cs["hash"]]
        )
        self.expect_expiration_date = datetime.fromisoformat(
            self.credential["credential"]["expirationDate"]
        )
