from unittest import mock

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from ninja_jwt.schema import RefreshToken

from account.deduplication import Rules
from account.deduplication.lifo import HashScorerLinkIntegrityError, alifo
from account.models import Account, Community
from registry.models import HashScorerLink, Passport, Stamp
from scorer_weighted.models import Scorer, WeightedScorer

User = get_user_model()

mock_community_body = {"name": "test", "description": "test"}

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
        # We create 1 passport for each community, and add 1 stamps to it
        passport1 = await Passport.objects.acreate(
            address="0xaddress_1", community=self.community1
        )
        await Stamp.objects.acreate(
            passport=passport1,
            provider="test_provider",
            credential=self.credential,
        )

        # We create 1 passport for each community, and add 1 stamps to it
        passport2 = await Passport.objects.acreate(
            address="0xaddress_2", community=self.community2
        )
        await Stamp.objects.acreate(
            passport=passport2,
            provider="test_provider",
            credential=self.credential,
        )

        deduped_passport, _, clashing_stamps = await alifo(
            passport1.community,
            {"stamps": [self.credential]},
            passport1.address,
        )
        # We expect the passport not to be deduped, as the duplicate hash is
        # contained in a different community
        self.assertEqual(len(deduped_passport["stamps"]), 1)
        self.assertEqual(clashing_stamps, {})

    @async_to_sync
    async def test_lifo_no_deduplicate_same_passport_address_across_cummunities(self):
        """
        Test that the deduplication method is not deduplicating stamps owned by the
        same address across communities.
        This means the user can submit the same stamps to different communities with the
        same ETH address, and they will not be discarded by the `lifo` deduplication method
        """
        # We create 1 passport for each community, and add 1 stamps to it
        passport1 = await Passport.objects.acreate(
            address="0xaddress_1", community=self.community1
        )
        await Stamp.objects.acreate(
            passport=passport1,
            provider="test_provider",
            credential=self.credential,
        )

        # We create the 2nd passport, owned by the same address and add the same stamp to it
        passport2 = await Passport.objects.acreate(
            address=passport1.address, community=self.community2
        )
        await Stamp.objects.acreate(
            passport=passport2,
            provider="test_provider",
            credential=self.credential,
        )

        deduped_passport, _, clashing_stamps = await alifo(
            passport1.community,
            {"stamps": [self.credential]},
            passport1.address,
        )

        # We expect the passport not to be deduped, as the duplicate hash is
        # contained in a different community
        self.assertEqual(len(deduped_passport["stamps"]), 1)
        self.assertEqual(clashing_stamps, {})

    @async_to_sync
    async def test_lifo_deduplicate(self):
        """
        Verifies that deduplication works if the user submits the same stamps to a community
        but as part of different passports
        """
        passport = await Passport.objects.acreate(
            address="0xaddress_1", community=self.community1
        )

        # We test deduplication of the 1st passport (for example user submits the same passport again)
        deduped_passport, _, clashing_stamps = await alifo(
            passport.community,
            {"stamps": [self.credential]},
            passport.address,
        )
        stamp = deduped_passport["stamps"][0]
        await Stamp.objects.acreate(
            passport=passport,
            provider=stamp["credential"]["credentialSubject"]["provider"],
            credential=stamp["credential"],
        )

        # We expect the passport to not be deduped, as it is the same owner
        self.assertEqual(len(deduped_passport["stamps"]), 1)
        self.assertEqual(clashing_stamps, {})
        # We test deduplication of another passport with different address but
        # with the same stamp
        deduped_passport, _, clashing_stamps = await alifo(
            passport.community, {"stamps": [self.credential]}, "0xaddress_2"
        )

        # We expect the passport to be deduped, and the return copy shall contain
        # no stamps
        self.assertEqual(len(deduped_passport["stamps"]), 0)
        self.assertEqual(
            clashing_stamps,
            {
                "test_provider": self.credential,
            },
        )

    def test_retry_on_clash(self):
        """
        This tests functionality that causes the deduplication method to retry
        when there is a collision with another deduplication happening at the
        same time. It's not possible to test this directly, so instead we're
        sending in a payload with two stamps with the same credential, which
        wouldn't make it past the previous validation step in the real flow.
        """

        passport = Passport.objects.create(
            address="0xaddress_1", community=self.community1
        )

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
                    passport.community,
                    {
                        "stamps": [
                            self.credential,
                            self.credential,
                        ]
                    },
                    passport.address,
                )
        self.assertEqual(call_count, 5)


class LifoDeduplicationWith2NullifiersTestCase(LifoDeduplicationWith1NullifierTestCase):
    def setUp(self):
        super().setUp()
        self.credential = credential_with_2_nullifiers
