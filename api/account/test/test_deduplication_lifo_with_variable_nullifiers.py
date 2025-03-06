from datetime import datetime, timedelta, timezone

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from ninja_jwt.schema import RefreshToken

from account.deduplication import Rules
from account.deduplication.lifo import alifo
from account.models import Account, Community
from registry.models import HashScorerLink, Passport, Stamp
from scorer_weighted.models import Scorer, WeightedScorer

User = get_user_model()

mock_community_body = {"name": "test", "description": "test"}

credential_with_nullifier_a = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v1:test_hash - A"],
            "provider": "test_provider",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}

credential_with_nullifier_b = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v2:test_hash - B"],
            "provider": "test_provider",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}

credential_with_2_nullifiers = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v1:test_hash - A", "v2:test_hash - B"],
            "provider": "test_provider",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}

credential_with_2_nullifiers_a_and_random = {
    "credential": {
        "credentialSubject": {
            "nullifiers": ["v1:test_hash - A", "v2:test_hash - random"],
            "provider": "test_provider",
        },
        "expirationDate": "2099-02-21T15:30:51.720Z",
    },
}


class LifoDeduplicationWithVariableNullifiersTestCase(TransactionTestCase):
    def setUp(self):
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
    async def test_lifo_deduplication_on_either_nullifier_when_first_has_2(self):
        """
        Assuming the initial deduplication was on 2 nullifiers, when subsequent
        ones are attempted using only one of the nullifiers, the stamp will be deduped
        """
        passport = await Passport.objects.acreate(
            address="0xaddress_1", community=self.community1
        )

        # We test deduplication of the 1st passport (for example user submits the same passport again)
        deduped_passport, _, clashing_stamps = await alifo(
            passport.community,
            {"stamps": [credential_with_2_nullifiers]},
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
        # a stamp with one of the previous nullifiers - A
        deduped_passport, _, clashing_stamps = await alifo(
            passport.community, {"stamps": [credential_with_nullifier_a]}, "0xaddress_2"
        )

        self.assertEqual(len(deduped_passport["stamps"]), 0)
        self.assertEqual(
            clashing_stamps,
            {
                "test_provider": credential_with_nullifier_a,
            },
        )

        # We test deduplication of another passport with different address but
        # a stamp with one of the previous nullifiers - B
        deduped_passport, _, clashing_stamps = await alifo(
            passport.community, {"stamps": [credential_with_nullifier_b]}, "0xaddress_2"
        )

        self.assertEqual(len(deduped_passport["stamps"]), 0)
        self.assertEqual(
            clashing_stamps,
            {
                "test_provider": credential_with_nullifier_b,
            },
        )

    @async_to_sync
    async def test_lifo_deduplication_on_either_nullifier_when_first_has_1(self):
        """
        Assuming the initial deduplication was on 1 nullifiers, when subsequent
        ones are attempted using only stamps with multiple nullifiers, the stamp will be deduped
        """
        passport = await Passport.objects.acreate(
            address="0xaddress_1", community=self.community1
        )

        # We test deduplication of the 1st passport (for example user submits the same passport again)
        deduped_passport, _, clashing_stamps = await alifo(
            passport.community,
            {"stamps": [credential_with_nullifier_a]},
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
        # a stamp with one of the previous nullifiers - A
        deduped_passport, _, clashing_stamps = await alifo(
            passport.community,
            {"stamps": [credential_with_2_nullifiers_a_and_random]},
            "0xaddress_2",
        )

        self.assertEqual(len(deduped_passport["stamps"]), 0)
        self.assertEqual(
            clashing_stamps,
            {
                "test_provider": credential_with_2_nullifiers_a_and_random,
            },
        )

    @async_to_sync
    async def test_lifo_deduplication_backfill(self):
        """
        Let's asume a stamp using a nullifier "A" only was already used and has a HashScorerLink.
        When another user trys 1st deduplication of the same stamp nullifiers ["A", "B"]
        then the HashScorerLink for nullifier "B" does not exist.

        We want to make sure the HashScorerLink for nullifier "B" is backfilled.
        """
        now = datetime.now(timezone.utc)
        expiration_date_1 = now + timedelta(days=3)
        expiration_date_2 = now + timedelta(days=10)
        expiration_date_3 = now + timedelta(days=15)
        credential_a = {
            "credential": {
                "credentialSubject": {
                    "nullifiers": ["hash-A"],  # only 1 nullifier
                    "provider": "test_provider",
                },
                "expirationDate": expiration_date_1.isoformat(),  # expiring date
            },
        }

        credential_ab = {
            "credential": {
                "credentialSubject": {
                    "nullifiers": ["hash-A", "hash-B"],  # 2 nullifier
                    "provider": "test_provider",
                },
                "expirationDate": expiration_date_2.isoformat(),  # expiring date is newer
            },
        }

        credential_b = {
            "credential": {
                "credentialSubject": {
                    "nullifiers": ["hash-B"],  # 2 nullifier
                    "provider": "test_provider",
                },
                "expirationDate": expiration_date_3.isoformat(),  # expiring date is newer
            },
        }

        ##################################################
        # Make the 1st deduplication - hash-A
        ##################################################
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_a]},
            "0xaddress_1",
        )
        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community1
            ).values_list("hash", "expires_at")
        ]
        self.assertListEqual(hash_links, [("hash-A", expiration_date_1)])
        self.assertDictEqual(deduped_passport, {"stamps": [credential_a]})
        self.assertDictEqual(clashing_stamps, {})

        # Make the 2nd deduplication - hash-A, hash-B
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_ab]},
            "0xaddress_2",
        )

        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links, [("hash-A", expiration_date_1), ("hash-B", expiration_date_1)]
        )  # Expect hash-B to have been back-filled, expiration date is the same for all
        self.assertDictEqual(deduped_passport, {"stamps": []})
        self.assertDictEqual(clashing_stamps, {"test_provider": credential_ab})

        ##################################################
        # Make the 3rd deduplication - hash-B
        ##################################################
        deduped_passport, _, clashing_stamps = await alifo(
            self.community1,
            {"stamps": [credential_b]},
            "0xaddress_2",
        )

        hash_links = [
            h
            async for h in HashScorerLink.objects.filter(
                address="0xaddress_1", community=self.community1
            )
            .values_list("hash", "expires_at")
            .order_by("hash")
        ]
        self.assertListEqual(
            hash_links, [("hash-A", expiration_date_1), ("hash-B", expiration_date_1)]
        )  # Expect no changes here compared to previous step
        self.assertDictEqual(deduped_passport, {"stamps": []})
        self.assertDictEqual(clashing_stamps, {"test_provider": credential_b})
