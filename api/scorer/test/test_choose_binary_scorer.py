"""Select Binary Scorer feature tests."""

import json

import pytest
from unittest.mock import patch
from account.models import Community
from django.test import Client
from pytest_bdd import given, scenario, then, when
from scorer_weighted.models import BinaryWeightedScorer
from registry.test.test_passport_submission import mock_passport

pytestmark = pytest.mark.django_db


@scenario(
    "features/choose_binary_scorer.feature",
    "As a developer, I want to choose the Gitcoin Binary Community Score",
)
def test_as_a_developer_i_want_to_choose_the_gitcoin_binary_community_score():
    """As a developer, I want to choose the Gitcoin Binary Community Score."""


@given(
    "that I select the Gitcoin Binary Community Score as an option",
    target_fixture="scorersPutResponse",
)
def scorersPutResponse(access_token, scorer_community):
    scorer = scorer_community.scorer
    client = Client()
    return client.put(
        f"/account/communities/{scorer_community.id}/scorers",
        json.dumps({"scorer_type": scorer.Type.WEIGHTED_BINARY}),
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )


@when("the selection takes effect")
def _(scorersPutResponse):
    assert scorersPutResponse.status_code == 200
    assert scorersPutResponse.json() == {
        "ok": True,
    }


@then("it automatically becomes the new rule in the respective community")
def _(scorer_community):
    scorer = Community.objects.get(id=scorer_community.id).scorer
    assert scorer.type == "WEIGHTED_BINARY"
    assert scorer.binaryweightedscorer
    assert type(scorer.binaryweightedscorer) == BinaryWeightedScorer


@when("I choose to score a passport", target_fixture="scoreResponse")
def scoreResponse(scorer_community, scorer_api_key):
    """I choose to score a passport."""
    with patch("registry.api.get_passport", return_value=mock_passport) as get_passport:
        with patch(
            "registry.api.validate_credential", side_effect=[[], []]
        ) as validate_credential:
            client = Client()
            return client.post(
                "/registry/submit-passport",
                json.dumps(
                    {
                        "community": scorer_community.id,
                        "address": "0x0123",
                    }
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
            )


@then("the binary score should be returned")
def _(scoreResponse):
    """the binary score should be returned."""
    assert scoreResponse.json()[0]["score"] == "1.000000000"


@then("the raw score should be returned")
def _(scoreResponse):
    """the raw score should be returned."""
    assert float(scoreResponse.json()[0]["evidence"][0]["rawScore"]) > 0


@then("the threshold should be returned")
def _(scoreResponse):
    """the threshold should be returned."""
    assert scoreResponse.json()[0]["evidence"][0]["threshold"] == "3.00000"
