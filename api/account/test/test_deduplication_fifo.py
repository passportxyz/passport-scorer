import json

from account.deduplication import Rules
from account.deduplication.fifo import fifo
from account.models import Account, Community
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.schema import RefreshToken
from registry.models import Passport, Stamp
from scorer_weighted.models import Scorer, WeightedScorer

User = get_user_model()

mock_community_body = {"name": "test", "description": "test"}


class FifoDeduplication(TestCase):
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
            name="Community1", scorer=scorer1, rule=Rules.FIFO, account=self.account1
        )

        (self.account2, _) = Account.objects.get_or_create(
            user=self.user2, defaults={"address": "0x0"}
        )
        scorer2 = WeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED, weights={"test_provider": 10}
        )
        self.community2 = Community.objects.create(
            name="Community2", scorer=scorer2, rule=Rules.FIFO, account=self.account2
        )

    def test_fifo_only_removes_deduplicate_in_passport_community(self):
        """
        Test that the deduplicate stamps are found, deleted, and passport score is updated
        """
        # We create 1 passport for each community, and add 1 stamps to it
        credential = {"credential": {"credentialSubject": {"hash": "test_hash"}}}
        passport1 = Passport.objects.create(
            address="0xaddress_1", passport={}, community=self.community1
        )

        passport2 = Passport.objects.create(
            address="0xaddress_2", passport={}, community=self.community1
        )

        Stamp.objects.create(
            passport=passport1,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        Stamp.objects.create(
            passport=passport2,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        # We call the `fifo` deduplication method
        fifo(
            community=self.community1,
            fifo_passport={"stamps": [credential]},
            address=passport1.address,
        )

        # We check that the `deduplicated_stamps` queryset contains the stamp we added
        self.assertEqual(
            passport2.stamps.count(),
            0,
            "The stamp should have been deleted from the passport",
        )

        self.assertEqual(
            passport1.stamps.count(),
            1,
            "The stamp should not have been deleted from the passpo",
        )

    def test_fifo_removes_duplicates_from_within_community(self):
        """
        Test that the deduplicate stamps are found, deleted, and passport score is updated
        """
        # We create 1 passport for each community, and add 1 stamps to it
        credential = {"credential": {"credentialSubject": {"hash": "test_hash"}}}
        passport1 = Passport.objects.create(
            address="0xaddress_1", passport={}, community=self.community1
        )

        passport2 = Passport.objects.create(
            address="0xaddress_2", passport={}, community=self.community1
        )

        Stamp.objects.create(
            passport=passport1,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        Stamp.objects.create(
            passport=passport2,
            hash="test_hash",
            provider="test_provider",
            credential=credential,
        )

        # We call the `fifo` deduplication method
        fifo(
            community=self.community1,
            fifo_passport={"stamps": [credential]},
            address=passport1.address,
        )

        # We check that the `deduplicated_stamps` queryset contains the stamp we added
        self.assertEqual(
            passport2.stamps.count(),
            0,
            "The stamp should have been deleted from the passport",
        )

        self.assertEqual(
            passport1.stamps.count(),
            1,
            "The stamp should not have been deleted from the passpo",
        )
