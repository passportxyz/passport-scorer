import pytest
from registry.models import Passport, Stamp
from scorer_weighted.models import BinaryWeightedScorer

pytestmark = pytest.mark.django_db


@pytest.fixture(name="weighted_scorer_passports")
def fixture_weighted_scorer_passports(
    passport_holder_addresses, scorer_community_with_binary_scorer
):
    passport = Passport.objects.create(
        address=passport_holder_addresses[0]["address"],
        passport={},
        community=scorer_community_with_binary_scorer,
    )
    Stamp.objects.create(
        passport=passport,
        provider="Facebook",
        hash="0x1234",
        credential={},
    )

    passport1 = Passport.objects.create(
        address=passport_holder_addresses[1]["address"],
        passport={},
        community=scorer_community_with_binary_scorer,
    )

    Stamp.objects.create(
        passport=passport1,
        provider="Facebook",
        hash="0x12345",
        credential={},
    )
    Stamp.objects.create(
        passport=passport1,
        provider="Google",
        hash="0x123456",
        credential={},
    )

    passport2 = Passport.objects.create(
        address=passport_holder_addresses[2]["address"],
        passport={},
        community=scorer_community_with_binary_scorer,
    )

    Stamp.objects.create(
        passport=passport2,
        provider="Facebook",
        hash="0x12345a",
        credential={},
    )
    Stamp.objects.create(
        passport=passport2,
        provider="Google",
        hash="0x123456ab",
        credential={},
    )
    Stamp.objects.create(
        passport=passport2,
        provider="Ens",
        hash="0x123456abc",
        credential={},
    )

    return [passport, passport1, passport2]


class TestBinaraWeightedScorer:
    def test_binary_weighted_scorer(self, weighted_scorer_passports):
        scorer = BinaryWeightedScorer(
            threshold=2, weights={"Facebook": 1, "Google": 1, "Ens": 1}
        )
        scorer.save()

        scores = scorer.compute_score([p.id for p in weighted_scorer_passports])
        assert scores == [0, 1, 1]
