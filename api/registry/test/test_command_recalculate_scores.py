import json

import pytest
from account.models import Community
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from registry.models import Passport, Score, Stamp

pytestmark = pytest.mark.django_db

current_weights = settings.GITCOIN_PASSPORT_WEIGHTS


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
        provider="FirstEthTxnProvider",
        hash="0x1234",
        credential={},
    )

    passport1 = Passport.objects.create(
        address=passport_holder_addresses[1]["address"],
        community=scorer_community_with_binary_scorer,
    )

    Stamp.objects.create(
        passport=passport1,
        provider="FirstEthTxnProvider",
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
        provider="FirstEthTxnProvider",
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
        provider="FirstEthTxnProvider",
        hash="0x1234",
        credential={},
    )

    passport1 = Passport.objects.create(
        address=passport_holder_addresses[1]["address"],
        community=scorer_community_with_weighted_scorer,
    )

    Stamp.objects.create(
        passport=passport1,
        provider="FirstEthTxnProvider",
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
        provider="FirstEthTxnProvider",
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

    updated_weights = {
        "FirstEthTxnProvider": "75",
        "Google": "1",
        "Ens": "1",
    }

    @override_settings(GITCOIN_PASSPORT_WEIGHTS=updated_weights)
    def test_rescoring_binary_scorer_w_updated_settings(
        self,
        binary_weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_binary_scorer,
    ):
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

        # Expect all scores to be above threshold
        for s in scores:
            assert s.score == 1
            assert s.status == "DONE"
            assert s.error == None

        s1 = Score.objects.get(passport=binary_weighted_scorer_passports[0])
        assert s1.evidence["rawScore"] == "75"
        assert len(s1.stamp_scores) == 1
        assert "FirstEthTxnProvider" in s1.stamp_scores

        s2 = Score.objects.get(passport=binary_weighted_scorer_passports[1])
        assert s2.evidence["rawScore"] == "76"
        assert len(s2.stamp_scores) == 2
        assert "FirstEthTxnProvider" in s2.stamp_scores
        assert "Google" in s2.stamp_scores

        s3 = Score.objects.get(passport=binary_weighted_scorer_passports[2])
        assert s3.evidence["rawScore"] == "77"
        assert len(s3.stamp_scores) == 3
        assert "FirstEthTxnProvider" in s3.stamp_scores
        assert "Google" in s3.stamp_scores
        assert "Ens" in s3.stamp_scores

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
        assert len(s1.stamp_scores) == 1
        assert "FirstEthTxnProvider" in s1.stamp_scores

        s2 = Score.objects.get(passport=weighted_scorer_passports[1])
        assert s2.score == 2
        assert len(s2.stamp_scores) == 2
        assert "FirstEthTxnProvider" in s2.stamp_scores
        assert "Google" in s2.stamp_scores

        s3 = Score.objects.get(passport=weighted_scorer_passports[2])
        assert s3.score == 3
        assert len(s3.stamp_scores) == 3
        assert "FirstEthTxnProvider" in s3.stamp_scores
        assert "Google" in s3.stamp_scores
        assert "Ens" in s3.stamp_scores

    updated_weights = {
        "FirstEthTxnProvider": "75",
        "Google": "1",
        "Ens": "1",
    }

    @override_settings(GITCOIN_PASSPORT_WEIGHTS=updated_weights)
    def test_rescoring_weighted_scorer_w_updated_settings(
        self,
        weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
    ):
        """Change weights and rescore ..."""
        community = scorer_community_with_weighted_scorer
        args = []
        opts = {}

        scores = list(Score.objects.all())

        scorer = community.get_scorer()

        # Check the initial threshold
        assert len(scores) == 0
        call_command("recalculate_scores", *args, **opts)
        scorer.weights["FirstEthTxnProvider"] = 75
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
        assert len(s1.stamp_scores) == 1
        assert "FirstEthTxnProvider" in s1.stamp_scores

        s2 = Score.objects.get(passport=weighted_scorer_passports[1])
        assert s2.score == 76
        assert len(s2.stamp_scores) == 2
        assert "FirstEthTxnProvider" in s2.stamp_scores
        assert "Google" in s2.stamp_scores

        s3 = Score.objects.get(passport=weighted_scorer_passports[2])
        assert s3.score == 77
        assert len(s3.stamp_scores) == 3
        assert "FirstEthTxnProvider" in s3.stamp_scores
        assert "Google" in s3.stamp_scores
        assert "Ens" in s3.stamp_scores

    def test_rescoring_include_filter(
        self,
        weighted_scorer_passports,
        binary_weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
        scorer_community_with_binary_scorer,
    ):
        """Test the recalculate_scores command uses the include filter properly"""

        communities = list(Community.objects.all())
        # Make sure the pre-test condition is fulfilled we have 2 communities
        # and each one has at least 1 passport
        assert len(communities) == 2
        for c in Community.objects.all():
            assert c.passports.count() > 0

        included_community = communities[0]
        excluded_community = communities[1]

        call_command(
            "recalculate_scores",
            *[],
            **{
                "filter_community_include": json.dumps({"id": included_community.id}),
            },
        )

        # We check for scores only in the included community
        # and make sure the ones for exluded community have not been calculated
        Score.objects.filter(passport__community=excluded_community).count() == 0
        Score.objects.filter(passport__community=included_community).count() == len(
            weighted_scorer_passports
        )

    def test_rescoring_exclude_filter(
        self,
        weighted_scorer_passports,
        binary_weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
        scorer_community_with_binary_scorer,
    ):
        """Test the recalculate_scores command uses the exclude filter properly"""

        # Make sure the pre-test condition is fulfilled we have 2 communities
        # and each one has at least 1 passport
        assert len(weighted_scorer_passports) > 0
        assert len(binary_weighted_scorer_passports) > 0
        communities = list(Community.objects.all())
        assert len(communities) == 2

        included_community = scorer_community_with_weighted_scorer
        excluded_community = scorer_community_with_binary_scorer

        call_command(
            "recalculate_scores",
            *[],
            **{
                "filter_community_exclude": json.dumps({"id": excluded_community.id}),
            },
        )

        # We check for scores only in the included community
        # and make sure the ones for exluded community have not been calculated
        Score.objects.filter(passport__community=excluded_community).count() == 0
        Score.objects.filter(passport__community=included_community).count() == len(
            weighted_scorer_passports
        )

    def test_rescoring_no_filter(
        self,
        weighted_scorer_passports,
        binary_weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
        scorer_community_with_binary_scorer,
    ):
        """Test the recalculate_scores command re-calculates all scores for all communities with no include or exclude filter"""

        # Make sure the pre-test condition is fulfilled we have 2 communities
        # and each one has at least 1 passport
        assert len(weighted_scorer_passports) > 0
        assert len(binary_weighted_scorer_passports) > 0
        communities = list(Community.objects.all())
        assert len(communities) == 2

        included_community = scorer_community_with_weighted_scorer
        excluded_community = scorer_community_with_binary_scorer

        call_command(
            "recalculate_scores",
            *[],
            **{},
        )

        # We check for scores only in the included community
        # and make sure the ones for exluded community have not been calculated
        Score.objects.filter(passport__community=excluded_community).count() == len(
            binary_weighted_scorer_passports
        )
        Score.objects.filter(passport__community=included_community).count() == len(
            weighted_scorer_passports
        )
