import json

from account.deduplication import Rules
from account.deduplication.lifo import lifo
from account.models import Account, Community
from django.conf import settings
from django.test import TestCase
from ninja_jwt.schema import RefreshToken
from registry.models import Passport, Stamp
from scorer_weighted.models import Scorer, WeightedScorer

mock_community_body = {"name": "test", "description": "test"}

User = settings.AUTH_USER_MODEL


class LifoDeduplicationTestCase(TestCase):
    def setUp(self):
        User.objects.create_user(username="admin", password="12345")

        self.user = User.objects.create_user(username="testuser-1", password="12345")
        self.user2 = User.objects.create_user(username="testuser-2", password="12345")

        refresh = RefreshToken.for_user(self.user)
        self.access_token = refresh.access_token

        (self.account1, _) = Account.objects.get_or_create(
            user=self.user, defaults={"address": "0x0"}
        )
        scorer1 = WeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED, weights={"test_provider": 10}
        )
        self.community1 = Community.objects.create(
            name="Community1", scorer=scorer1, rules=Rules.LIFO, account=self.account1
        )

        (self.account2, _) = Account.objects.get_or_create(
            user=self.user2, defaults={"address": "0x0"}
        )
        scorer2 = WeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED, weights={"test_provider": 10}
        )
        self.community2 = Community.objects.create(
            name="Community2", scorer=scorer2, rules=Rules.LIFO, account=self.account2
        )

    def test_lifo_no_deduplicate_across_cummunities(self):
        """
        Test that the deduplication method is not deduplicating stamps across communities.
        This means the user can submit the same stamps to different communities, and they will not
        be discarded by the `lifo` deduplication method
        """
        # We create 1 passport for each community, and add 1 stamps to it
        credential = {"credential": {"credentialSubject": {"hash": "test_hash"}}}
        passport1 = Passport.objects.create(
            address="0xaddress_1", passport={}, community=self.community1
        )
        Stamp.objects.create(
            passport=passport1,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        # We create 1 passport for each community, and add 1 stamps to it
        passport2 = Passport.objects.create(
            address="0xaddress_2", passport={}, community=self.community2
        )
        Stamp.objects.create(
            passport=passport2,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        deduped_passport = lifo(
            passport1.community, {"stamps": [credential]}, passport1.address
        )

        # We expect the passport not to be deduped, as the duplicate hash is
        # contained in a different community
        self.assertEqual(len(deduped_passport["stamps"]), 1)

    def test_lifo_no_deduplicate_same_passport_address_across_cummunities(self):
        """
        Test that the deduplication method is not deduplicating stamps owned by the
        same address across communities.
        This means the user can submit the same stamps to different communities with the
        same ETH address, and they will not be discarded by the `lifo` deduplication method
        """
        # We create 1 passport for each community, and add 1 stamps to it
        credential = {"credential": {"credentialSubject": {"hash": "test_hash"}}}
        passport1 = Passport.objects.create(
            address="0xaddress_1", passport={}, community=self.community1
        )
        Stamp.objects.create(
            passport=passport1,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        # We create the 2nd passport, owned by the same addres and add the same stamp to it
        passport2 = Passport.objects.create(
            address=passport1.address, passport={}, community=self.community2
        )
        Stamp.objects.create(
            passport=passport2,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        deduped_passport = lifo(
            passport1.community, {"stamps": [credential]}, passport1.address
        )

        # We expect the passport not to be deduped, as the duplicate hash is
        # contained in a different community
        self.assertEqual(len(deduped_passport["stamps"]), 1)

    def test_lifo_deduplicate(self):
        """
        Verifies that deduplication works if the user submits the same stamps to a community
        but as part of different passports
        """
        # We create 1 passport for each community, and add 1 stamps to it
        credential = {"credential": {"credentialSubject": {"hash": "test_hash"}}}
        passport = Passport.objects.create(
            address="0xaddress_1", passport={}, community=self.community1
        )
        Stamp.objects.create(
            passport=passport,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        # We test deduplication of the 1st passport (for example user submits the same passport again)
        deduped_passport = lifo(
            passport.community, {"stamps": [credential]}, passport.address
        )

        # We expect the passport to not be deduped, as it is the same owner
        self.assertEqual(len(deduped_passport["stamps"]), 1)

        # We test deduplication of another passport with different address but
        # with the same stamp
        deduped_passport = lifo(
            passport.community, {"stamps": [credential]}, "0xaddress_2"
        )

        # We expect the passport to be deduped, and the return copy shall contain
        # no stamps
        self.assertEqual(len(deduped_passport["stamps"]), 0)
