"""Select Binary Scorer feature tests."""

import json

import pytest
from account.models import Community
from django.test import Client
from pytest_bdd import given, scenario, then, when
from scorer_weighted.models import BinaryWeightedScorer

pytestmark = pytest.mark.django_db


@scenario(
    "features/choose_binary_scorer.feature",
    "As a developer, I want to choose the Gitcoin Binary Community Score",
)
def test_as_a_developer_i_want_to_choose_the_gitcoin_binary_community_score():
    """As a developer, I want to choose the Gitcoin Binary Community Score."""


@given("that I select the Gitcoin Binary Community Score as an option")
def _():
    pass


@when("the selection takes effect")
def _(access_token, scorer_community):
    scorer = scorer_community.scorer
    client = Client()
    response = client.put(
        f"/account/communities/{scorer_community.id}/scorers",
        json.dumps({"scorer_type": scorer.Type.WEIGHTED_BINARY}),
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
    }


@then("it automatically becomes the new rule in the respective community")
def _(scorer_community):
    scorer = Community.objects.get(id=scorer_community.id).scorer
    assert (scorer.type == "WEIGHTED_BINARY")
    assert (scorer.binaryweightedscorer)
    assert (type(scorer.binaryweightedscorer) == BinaryWeightedScorer)
