import json
from decimal import Decimal

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings

from account.models import Community
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
        provider="FirstEthTxnProvider",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )

    passport1 = Passport.objects.create(
        address=passport_holder_addresses[1]["address"],
        community=scorer_community_with_binary_scorer,
    )

    Stamp.objects.create(
        passport=passport1,
        provider="FirstEthTxnProvider",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )
    Stamp.objects.create(
        passport=passport1,
        provider="Google",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )

    passport2 = Passport.objects.create(
        address=passport_holder_addresses[2]["address"],
        community=scorer_community_with_binary_scorer,
    )

    Stamp.objects.create(
        passport=passport2,
        provider="FirstEthTxnProvider",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )
    Stamp.objects.create(
        passport=passport2,
        provider="Google",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )
    Stamp.objects.create(
        passport=passport2,
        provider="Ens",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
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
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )

    passport1 = Passport.objects.create(
        address=passport_holder_addresses[1]["address"],
        community=scorer_community_with_weighted_scorer,
    )

    Stamp.objects.create(
        passport=passport1,
        provider="FirstEthTxnProvider",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )
    Stamp.objects.create(
        passport=passport1,
        provider="Google",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )

    passport2 = Passport.objects.create(
        address=passport_holder_addresses[2]["address"],
        community=scorer_community_with_weighted_scorer,
    )

    Stamp.objects.create(
        passport=passport2,
        provider="FirstEthTxnProvider",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )
    Stamp.objects.create(
        passport=passport2,
        provider="Google",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )
    Stamp.objects.create(
        passport=passport2,
        provider="Ens",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
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
        assert scorer.threshold == Decimal(20)
        assert len(scores) == 0
        call_command("recalculate_scores", *args, **opts)

        scores = list(Score.objects.all())
        assert len(scores) == 3

        # Expect all scores to be below threshold
        for s in scores:
            assert s.score == 0
            assert s.status == "DONE"
            assert s.error is None

    @pytest.mark.parametrize(
        "weight_config",
        [
            {
                "FirstEthTxnProvider": "75",
                "Google": "1",
                "Ens": "1",
            }
        ],
        indirect=True,
    )
    def test_rescoring_binary_scorer_w_updated_settings(
        self,
        binary_weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_binary_scorer,
        weight_config,
    ):
        community = scorer_community_with_binary_scorer
        args = []
        opts = {}

        scores = list(Score.objects.all())

        scorer = community.get_scorer()

        # Check the initial threshold
        assert scorer.threshold == 20
        assert len(scores) == 0
        call_command("recalculate_scores", *args, **opts)

        scores = list(Score.objects.all())
        assert len(scores) == 3

        # Expect all scores to be above threshold
        for s in scores:
            assert s.score == 1
            assert s.status == "DONE"
            assert s.error is None

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

    @pytest.mark.parametrize(
        "weight_config",
        [
            {
                "FirstEthTxnProvider": "1",
                "Google": "1",
                "Ens": "1",
            }
        ],
        indirect=True,
    )
    def test_rescoring_weighted_scorer(
        self,
        weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
    ):
        """Test the recalculate_scores command for weighted scorer"""

        args = []
        opts = {}

        scores = list(Score.objects.all())

        # Check the initial threshold
        assert len(scores) == 0
        call_command("recalculate_scores", *args, **opts)

        scores = list(Score.objects.all())
        assert len(scores) == 3

        for s in scores:
            assert s.status == "DONE"
            assert s.error is None
            assert s.evidence is not None

        s1 = Score.objects.get(passport=weighted_scorer_passports[0])
        assert s1.evidence["rawScore"] == '1'
        assert len(s1.stamp_scores) == 1
        assert "FirstEthTxnProvider" in s1.stamp_scores

        s2 = Score.objects.get(passport=weighted_scorer_passports[1])
        assert s2.evidence["rawScore"] == '2'
        assert len(s2.stamp_scores) == 2
        assert "FirstEthTxnProvider" in s2.stamp_scores
        assert "Google" in s2.stamp_scores

        s3 = Score.objects.get(passport=weighted_scorer_passports[2])
        assert s3.evidence["rawScore"] == '3'
        assert len(s3.stamp_scores) == 3
        assert "FirstEthTxnProvider" in s3.stamp_scores
        assert "Google" in s3.stamp_scores
        assert "Ens" in s3.stamp_scores

    @pytest.mark.parametrize(
        "weight_config",
        [
            {
                "FirstEthTxnProvider": "75",
                "Google": "1",
                "Ens": "1",
            }
        ],
        indirect=True,
    )
    def test_rescoring_weighted_scorer_w_updated_settings(
        self,
        weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
        weight_config,
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
            assert s.error is None
            assert s.evidence is not None

        s1 = Score.objects.get(passport=weighted_scorer_passports[0])
        assert s1.evidence["rawScore"] == '75'
        assert len(s1.stamp_scores) == 1
        assert "FirstEthTxnProvider" in s1.stamp_scores

        s2 = Score.objects.get(passport=weighted_scorer_passports[1])
        assert s2.evidence["rawScore"] == '76'
        assert len(s2.stamp_scores) == 2
        assert "FirstEthTxnProvider" in s2.stamp_scores
        assert "Google" in s2.stamp_scores

        s3 = Score.objects.get(passport=weighted_scorer_passports[2])
        assert s3.evidence["rawScore"] == '77'
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
        # and make sure the ones for excluded community have not been calculated
        assert Score.objects.filter(passport__community=excluded_community).count() == 0
        assert Score.objects.filter(
            passport__community=included_community
        ).count() == len(weighted_scorer_passports)

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
        # and make sure the ones for excluded community have not been calculated
        assert Score.objects.filter(passport__community=excluded_community).count() == 0
        assert Score.objects.filter(
            passport__community=included_community
        ).count() == len(weighted_scorer_passports)

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

        call_command(
            "recalculate_scores",
            *[],
            **{},
        )

        assert Score.objects.filter(
            passport__community=scorer_community_with_binary_scorer
        ).count() == len(binary_weighted_scorer_passports)
        assert Score.objects.filter(
            passport__community=scorer_community_with_weighted_scorer
        ).count() == len(weighted_scorer_passports)

    def test_rescoring_excludes_communities_marked_for_exclusion(
        self,
        weighted_scorer_passports,
        binary_weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
        scorer_community_with_binary_scorer,
        capsys,
    ):
        """Test the recalculate_scores command excludes communities marked for exclusion"""

        # Make sure the pre-test condition is fulfilled we have 2 communities
        # and each one has at least 1 passport
        assert len(weighted_scorer_passports) > 0
        assert len(binary_weighted_scorer_passports) > 0
        communities = list(Community.objects.all())
        assert len(communities) == 2

        included_community = scorer_community_with_weighted_scorer
        excluded_community = scorer_community_with_binary_scorer

        scorer = excluded_community.get_scorer()
        scorer.exclude_from_weight_updates = True
        scorer.save()

        call_command(
            "recalculate_scores",
            *[],
            **{},
        )

        captured = capsys.readouterr()
        print(captured.out)
        assert "Updated scorers: 1" in captured.out
        assert included_community.name in captured.out
        assert excluded_community.name not in captured.out
        assert "Recalculating scores" in captured.out

    def test_only_weights_skips_rescore(
        self,
        weighted_scorer_passports,
        binary_weighted_scorer_passports,
        passport_holder_addresses,
        scorer_community_with_weighted_scorer,
        scorer_community_with_binary_scorer,
        capsys,
    ):
        """Test the recalculate_scores command excludes communities marked for exclusion"""

        # Make sure the pre-test condition is fulfilled we have 2 communities
        # and each one has at least 1 passport
        assert len(weighted_scorer_passports) > 0
        assert len(binary_weighted_scorer_passports) > 0
        communities = list(Community.objects.all())
        assert len(communities) == 2

        call_command(
            "recalculate_scores",
            *[],
            **{
                "only_weights": True,
            },
        )

        captured = capsys.readouterr()
        print(captured.out)
        assert "Updated scorers: 2" in captured.out
        assert "Recalculating scores" not in captured.out
