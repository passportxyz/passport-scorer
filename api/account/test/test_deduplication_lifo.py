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

# Test credentials for multi-nullifier feature flag testing
credential_with_mixed_nullifiers = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v0:test_hash", "v1:test_hash", "v2:test_hash"],
            "provider": "test_provider",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}

# Additional test credentials for clash testing
credential_with_v0_only = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v0:unique_hash"],
            "provider": "test_provider_v0",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}

credential_with_v1_clash = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v0:different_hash", "v1:test_hash"],
            "provider": "test_provider_v1_clash",
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


class MultiNullifierFeatureFlagTestCase(TransactionTestCase):
    """
    Test cases for the FF_MULTI_NULLIFIER feature flag functionality
    """

    def setUp(self):
        User.objects.create_user(username="admin", password="12345")
        self.user = User.objects.create_user(username="testuser-1", password="12345")
        self.user2 = User.objects.create_user(username="testuser-2", password="12345")

        (self.account1, _) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )
        scorer1 = WeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED, weights={"test_provider": 10}
        )
        self.community1 = Community.objects.create(
            name="Community1", scorer=scorer1, rule=Rules.LIFO, account=self.account1
        )

        self.expect_expiration_date = datetime.fromisoformat(
            credential_with_mixed_nullifiers["credential"]["expirationDate"]
        )

    @mock.patch("account.deduplication.lifo.settings.FF_MULTI_NULLIFIER", "off")
    @async_to_sync
    async def test_multi_nullifier_flag_off_filters_v0_only(self):
        """
        Test that when FF_MULTI_NULLIFIER is "off", only v0 nullifiers are processed
        """
        # Test with mixed nullifiers - should only process v0
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_with_mixed_nullifiers]},
            "0xaddress_1",
        )

        self.assertDictEqual(
            deduped_passport, {"stamps": [credential_with_mixed_nullifiers]}
        )
        self.assertDictEqual(clashing_stamps, {})

        # Check that only v0 nullifiers were stored
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
            [("v0:test_hash", self.expect_expiration_date)],
        )

    @mock.patch("account.deduplication.lifo.settings.FF_MULTI_NULLIFIER", "on")
    @async_to_sync
    async def test_multi_nullifier_flag_on_processes_all_nullifiers(self):
        """
        Test that when FF_MULTI_NULLIFIER is "on", all nullifiers are processed
        """
        # Test with mixed nullifiers - should process all
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_with_mixed_nullifiers]},
            "0xaddress_1",
        )

        self.assertDictEqual(
            deduped_passport, {"stamps": [credential_with_mixed_nullifiers]}
        )
        self.assertDictEqual(clashing_stamps, {})

        # Check that all nullifiers were stored
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        expected_nullifiers = ["v0:test_hash", "v1:test_hash", "v2:test_hash"]
        self.assertListEqual(
            hash_links,
            [
                (nullifier, self.expect_expiration_date)
                for nullifier in expected_nullifiers
            ],
        )

    @mock.patch("account.deduplication.lifo.settings.FF_MULTI_NULLIFIER", "off")
    @async_to_sync
    async def test_multi_nullifier_flag_off_no_clash_on_v1_only(self):
        """
        Test that when FF_MULTI_NULLIFIER is "off", a clash on v1 nullifier only
        does not trigger deduplication since v1 nullifiers are ignored
        """
        # First, submit a credential with mixed nullifiers to establish v1:test_hash
        await alifo(
            self.community1,
            {"stamps": [credential_with_mixed_nullifiers]},
            "0xaddress_1",
        )

        # Now submit a credential that has a clash on v1 but different v0
        # With flag off, this should NOT be deduplicated since only v0 is checked
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_with_v1_clash]},
            "0xaddress_2",
        )

        # Should not be deduplicated since v1 clash is ignored when flag is off
        self.assertDictEqual(deduped_passport, {"stamps": [credential_with_v1_clash]})
        self.assertDictEqual(clashing_stamps, {})

        # Check that the v0 nullifier from the new credential was stored
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
            [("v0:different_hash", self.expect_expiration_date)],
        )

    @mock.patch("account.deduplication.lifo.settings.FF_MULTI_NULLIFIER", "on")
    @async_to_sync
    async def test_multi_nullifier_flag_on_clash_on_v1_triggers_deduplication(self):
        """
        Test that when FF_MULTI_NULLIFIER is "on", a clash on v1 nullifier
        triggers deduplication even if v0 nullifiers are different
        """
        # First, submit a credential with mixed nullifiers to establish v1:test_hash
        await alifo(
            self.community1,
            {"stamps": [credential_with_mixed_nullifiers]},
            "0xaddress_1",
        )

        self.assertEqual(
            len(
                [
                    h
                    async for h in HashScorerLink.objects.filter(
                        address="0xaddress_1", community=self.community1
                    )
                ]
            ),
            3,
        )

        # Now submit a credential that has a clash on v1 but different v0
        # With flag on, this SHOULD be deduplicated due to v1 clash
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_with_v1_clash]},
            "0xaddress_2",
        )

        # Should be deduplicated due to v1 clash when flag is on
        self.assertDictEqual(deduped_passport, {"stamps": []})
        self.assertDictEqual(
            clashing_stamps,
            {
                "test_provider_v1_clash": credential_with_v1_clash,
            },
        )

        # Check that no hash links were created for address_2 due to deduplication
        address_2_hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_2", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(address_2_hash_links, [])

        # Check that the hash link for address_1 was backfilled
        self.assertEqual(
            len(
                [
                    h
                    async for h in HashScorerLink.objects.filter(
                        address="0xaddress_1", community=self.community1
                    )
                ]
            ),
            4,
        )

    @mock.patch("account.deduplication.lifo.settings.FF_MULTI_NULLIFIER", "off")
    @async_to_sync
    async def test_multi_nullifier_flag_off_v0_clash_still_triggers_deduplication(self):
        """
        Test that when FF_MULTI_NULLIFIER is "off", a clash on v0 nullifier
        still triggers deduplication as expected
        """
        # First, submit a credential with v0 nullifier
        await alifo(
            self.community1,
            {"stamps": [credential_with_v0_only]},
            "0xaddress_1",
        )

        # Now submit a credential that has the same v0 nullifier
        # This should be deduplicated regardless of flag state
        credential_with_same_v0 = {
            "credential": {
                "credentialSubject": {
                    "nullifiers": ["v0:unique_hash", "v1:different_v1_hash"],
                    "provider": "test_provider_same_v0",
                },
                "expirationDate": "2099-02-21T15:30:51.720Z",
            },
        }

        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_with_same_v0]},
            "0xaddress_2",
        )

        # Should be deduplicated due to v0 clash
        self.assertDictEqual(deduped_passport, {"stamps": []})
        self.assertDictEqual(
            clashing_stamps,
            {
                "test_provider_same_v0": credential_with_same_v0,
            },
        )

        # Check that no hash links were created for address_2 due to deduplication
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_2", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(hash_links, [])
