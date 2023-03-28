import json
from datetime import datetime, timedelta

import pytest
from account.deduplication import Rules
from account.deduplication.fifo import fifo
from account.models import Account, Community
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.schema import RefreshToken
from registry.models import Passport, Score, Stamp
from scorer_weighted.models import Scorer, WeightedScorer


class ExistingStamp:
    def __init__(self, hash):
        self.hash = hash


User = get_user_model()

mock_community_body = {"name": "test", "description": "test"}
google_credential = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..UvANt5nz16WNjkGTyUFIxbMBmYdEFZcVrD97L3EzOkvxz8eN-6UKeFZul_uPBfa88h50jKQgVgJlJqxR8kpSAQ",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:04.698Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:edgFWHsCSaqGxtHSqdiPpEXR06Ejw+YLO9K0BSjz0d8=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Google",
    },
}

mock_passport = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential},
    ],
}


class FifoDeduplication(TestCase):
    def setUp(self):
        self.create_test_users()
        self.create_test_communities()
        self.create_sample_passport()

    def create_test_users(self):
        User.objects.create_user(username="admin", password="12345")
        self.user = User.objects.create_user(username="testuser-1", password="12345")
        self.user2 = User.objects.create_user(username="testuser-2", password="12345")

        refresh = RefreshToken.for_user(self.user)
        self.access_token = refresh.access_token

    def create_test_communities(self):
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

    def create_sample_passport(self):
        self.sample_passport = {
            "stamps": [
                {"credential": {"credentialSubject": {"hash": "123"}}},
                {"credential": {"credentialSubject": {"hash": "456"}}},
                {"credential": {"credentialSubject": {"hash": "123"}}},
            ]
        }

    def test_fifo_removes_deduplicate_stamp_from_passport_in_same_community(self):
        """
        Test that the deduplicate stamps are found, deleted, and passport score is updated
        """
        passport1 = Passport.objects.create(
            address="0xaddress_1", community=self.community1
        )

        passport2 = Passport.objects.create(
            address="0xaddress_2", community=self.community1
        )

        Stamp.objects.create(
            passport=passport1,
            hash=google_credential["credentialSubject"]["hash"],
            provider="test_provider",
            credential=google_credential,
        )

        # We call the `fifo` deduplication method
        fifo(
            community=self.community1,
            fifo_passport=mock_passport,
            address=passport2.address,
        )

        updated_passport = Passport.objects.get(address="0xaddress_1")
        # We check that the `deduplicated_stamps` queryset contains the stamp we added

        self.assertEqual(
            updated_passport.stamps.count(),
            0,
            "The stamp should not have been deleted from the passpo",
        )

    def test_fifo_does_not_remove_deduplicate_stamp_from_passport_in_different_community(
        self,
    ):
        """
        Test that the deduplicate stamps are found, deleted, and passport score is updated
        """
        passport1 = Passport.objects.create(
            address="0xaddress_1", community=self.community2
        )

        passport2 = Passport.objects.create(
            address="0xaddress_2", community=self.community1
        )

        Stamp.objects.create(
            passport=passport1,
            hash=google_credential["credentialSubject"]["hash"],
            provider="test_provider",
            credential=google_credential,
        )

        # We call the `fifo` deduplication method
        fifo(
            community=self.community1,
            fifo_passport=mock_passport,
            address=passport2.address,
        )

        updated_passport = Passport.objects.get(address="0xaddress_1")
        # We check that the `deduplicated_stamps` queryset contains the stamp we added

        self.assertEqual(
            updated_passport.stamps.count(),
            1,
            "The stamp should not have been deleted from the passpo",
        )
