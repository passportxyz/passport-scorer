import pytest
from django.core.management import call_command
from registry.models import Passport, Score, Stamp

pytestmark = pytest.mark.django_db


@pytest.fixture(name="binary_weighted_scorer_passports")
def fixture_binaty_weighted_scorer_passports(
    passport_holder_addresses, scorer_community_with_binary_scorer
):
    passport = Passport.objects.create(
        address=passport_holder_addresses[0]["address"],
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


@pytest.fixture(name="weighted_scorer_passports")
def fixture_weighted_scorer_passports(
    passport_holder_addresses, scorer_community_with_weighted_scorer
):
    passport = Passport.objects.create(
        address=passport_holder_addresses[0]["address"],
        community=scorer_community_with_weighted_scorer,
    )
    Stamp.objects.create(
        passport=passport,
        provider="Facebook",
        hash="0x1234",
        credential={},
    )

    passport1 = Passport.objects.create(
        address=passport_holder_addresses[1]["address"],
        community=scorer_community_with_weighted_scorer,
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
        community=scorer_community_with_weighted_scorer,
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


class TestRecalculatScores:
    def test_rescoring_binary_scorer(
        self,
        binary_weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_binary_scorer,
    ):
        """Test the recalculate_scores command for binary scorer"""

        community = scorer_community_with_binary_scorer
        args = []
        opts = {}

        scores = list(Score.objects.all())

        scorer = community.get_scorer()

        # Check the initial threshold
        assert scorer.threshold == 75
        assert len(scores) == 0
        call_command("recalculate_scores", *args, **opts)

        scores = list(Score.objects.all())
        assert len(scores) == 3

        # Expect all scores to be below threshold
        for s in scores:
            assert s.score == 0
            assert s.status == "DONE"
            assert s.error == None

        #########################################################
        # Change weights and rescore ...
        #########################################################
        scorer.weights["Facebook"] = 75
        scorer.save()

        call_command("recalculate_scores", *args, **opts)

        scores = list(Score.objects.all())
        assert len(scores) == 3

        # Expect all scores to be above threshold
        for s in scores:
            assert s.score == 1
            assert s.status == "DONE"
            assert s.error == None

        s1 = Score.objects.get(passport=binary_weighted_scorer_passports[0])
        assert s1.evidence["rawScore"] == "75"
        assert len(s1.points) == 1
        assert "Facebook" in s1.points

        s2 = Score.objects.get(passport=binary_weighted_scorer_passports[1])
        assert s2.evidence["rawScore"] == "76"
        assert len(s2.points) == 2
        assert "Facebook" in s2.points
        assert "Google" in s2.points

        s3 = Score.objects.get(passport=binary_weighted_scorer_passports[2])
        assert s3.evidence["rawScore"] == "77"
        assert len(s3.points) == 3
        assert "Facebook" in s3.points
        assert "Google" in s3.points
        assert "Ens" in s3.points

    def test_rescoring_weighted_scorer(
        self,
        weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
    ):
        """Test the recalculate_scores command for weighted scorer"""

        community = scorer_community_with_weighted_scorer
        args = []
        opts = {}

        scores = list(Score.objects.all())

        scorer = community.get_scorer()

        # Check the initial threshold
        assert len(scores) == 0
        call_command("recalculate_scores", *args, **opts)

        scores = list(Score.objects.all())
        assert len(scores) == 3

        for s in scores:
            assert s.status == "DONE"
            assert s.error == None
            assert s.evidence == None

        s1 = Score.objects.get(passport=weighted_scorer_passports[0])
        assert s1.score == 1
        assert len(s1.points) == 1
        assert "Facebook" in s1.points

        s2 = Score.objects.get(passport=weighted_scorer_passports[1])
        assert s2.score == 2
        assert len(s2.points) == 2
        assert "Facebook" in s2.points
        assert "Google" in s2.points

        s3 = Score.objects.get(passport=weighted_scorer_passports[2])
        assert s3.score == 3
        assert len(s3.points) == 3
        assert "Facebook" in s3.points
        assert "Google" in s3.points
        assert "Ens" in s3.points

        #########################################################
        # Change weights and rescore ...
        #########################################################
        scorer.weights["Facebook"] = 75
        scorer.save()

        call_command("recalculate_scores", *args, **opts)

        scores = list(Score.objects.all())
        assert len(scores) == 3

        # Expect all scores to be above threshold
        for s in scores:
            assert s.status == "DONE"
            assert s.error == None
            assert s.evidence == None

        s1 = Score.objects.get(passport=weighted_scorer_passports[0])
        assert s1.score == 75
        assert len(s1.points) == 1
        assert "Facebook" in s1.points

        s2 = Score.objects.get(passport=weighted_scorer_passports[1])
        assert s2.score == 76
        assert len(s2.points) == 2
        assert "Facebook" in s2.points
        assert "Google" in s2.points

        s3 = Score.objects.get(passport=weighted_scorer_passports[2])
        assert s3.score == 77
        assert len(s3.points) == 3
        assert "Facebook" in s3.points
        assert "Google" in s3.points
        assert "Ens" in s3.points
