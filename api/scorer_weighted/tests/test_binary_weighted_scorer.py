from decimal import Decimal

import pytest
from registry.models import Passport, Stamp
from scorer_weighted.models import BinaryWeightedScorer
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.django_db

today = datetime.now(timezone.utc)
yesterday = today - timedelta(days=1)
one_day_before_yesterday = today - timedelta(days=2)
two_days_before_yesterday = today - timedelta(days=2)


@pytest.fixture(name="weighted_scorer_passports")
def fixture_weighted_scorer_passports(
    passport_holder_addresses, scorer_community_with_binary_scorer
):
    empty_passport = Passport.objects.create(
        address=passport_holder_addresses[0]["address"],
        community=scorer_community_with_binary_scorer,
    )

    passport = Passport.objects.create(
        address=passport_holder_addresses[1]["address"],
        community=scorer_community_with_binary_scorer,
    )
    Stamp.objects.create(
        passport=passport,
        provider="FirstEthTxnProvider",
        hash="0x1234",
        credential={
            "expirationDate": today.isoformat(),
        },
    )

    passport1 = Passport.objects.create(
        address=passport_holder_addresses[2]["address"],
        community=scorer_community_with_binary_scorer,
    )

    Stamp.objects.create(
        passport=passport1,
        provider="FirstEthTxnProvider",
        hash="0x12345",
        credential={
            "expirationDate": yesterday.isoformat(),
        },
    )
    Stamp.objects.create(
        passport=passport1,
        provider="Google",
        hash="0x123456",
        credential={
            "expirationDate": today.isoformat(),
        },
    )

    passport2 = Passport.objects.create(
        address=passport_holder_addresses[3]["address"],
        community=scorer_community_with_binary_scorer,
    )

    Stamp.objects.create(
        passport=passport2,
        provider="FirstEthTxnProvider",
        hash="0x12345a",
        credential={
            "expirationDate": one_day_before_yesterday.isoformat(),
        },
    )
    Stamp.objects.create(
        passport=passport2,
        provider="Google",
        hash="0x123456ab",
        credential={
            "expirationDate": yesterday.isoformat(),
        },
    )
    Stamp.objects.create(
        passport=passport2,
        provider="Ens",
        hash="0x123456abc",
        credential={
            "expirationDate": today.isoformat(),
        },
    )

    return [empty_passport, passport, passport1, passport2]


class TestBinaraWeightedScorer:
    def test_binary_weighted_scorer(self, weighted_scorer_passports):
        scorer = BinaryWeightedScorer(
            threshold=2, weights={"FirstEthTxnProvider": 1, "Google": 1, "Ens": 1}
        )
        scorer.save()

        scores = [
            s.score
            for s in scorer.compute_score([p.id for p in weighted_scorer_passports], 1)
        ]
        expiration_dates = [
            s.expiration_date
            for s in scorer.compute_score([p.id for p in weighted_scorer_passports], 1)
        ]
        assert scores == [Decimal(0), Decimal(0), Decimal(1), Decimal(1)]
        assert expiration_dates == [
            None,
            today,
            yesterday,
            one_day_before_yesterday,
        ]

    def test_duplicate_score_not_counted(
        self,
        weighted_scorer_passports,
    ):
        # Add a duplicate stamp

        Stamp.objects.create(
            passport=weighted_scorer_passports[1],
            provider="FirstEthTxnProvider",
            hash="0x12345",
            credential={
                "expirationDate": today.isoformat(),
            },
        )

        scorer = BinaryWeightedScorer(
            threshold=2, weights={"FirstEthTxnProvider": 1, "Google": 1, "Ens": 1}
        )
        scorer.save()

        scores = [
            s.score for s in scorer.compute_score([weighted_scorer_passports[1]], 1)
        ]
        assert scores == [Decimal(0)]
