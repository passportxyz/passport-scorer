"""Select Binary Scorer feature tests."""

import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from account.models import Community
from django.test import Client
from pytest_bdd import given, scenario, then, when
from registry.test.test_passport_submission import mock_passport
from scorer_weighted.models import BinaryWeightedScorer

pytestmark = pytest.mark.django_db

###################################################################################################
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
def scorers_put_response(access_token, scorer_community):
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
def score_response(scorer_community, scorer_api_key):
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
    assert scoreResponse.json()[0]["score"] == "0.000000000"


@then("the raw score should be returned")
def _(scoreResponse):
    """the raw score should be returned."""
    assert float(scoreResponse.json()[0]["evidence"][0]["rawScore"]) > 0


@then("the threshold should be returned")
def _(scoreResponse):
    """the threshold should be returned."""
    assert (
        scoreResponse.json()[0]["evidence"][0]["threshold"] == "74.00000"
    )  # That is the mocked value


###################################################################################################


@scenario("features/choose_binary_scorer.feature", 'Get score of "0.000000000"')
def test_get_score_of_000000():
    """Get score of "0.000000000"."""


@when(
    "I submit a passport that yields a weighted score less than the threshold",
    target_fixture="scoreResponseFor0",
)
def _(scorer_community_with_binary_scorer, scorer_api_key):
    """I submit a passport that yields a weighted score less than the threshold."""
    print("-" * 30)
    print(scorer_community_with_binary_scorer.scorer.binaryweightedscorer)
    print("-" * 30)
    with patch(
        "scorer_weighted.computation.calculate_weighted_score",
        return_value=[Decimal("70")],
    ) as calculate_weighted_score:
        with patch(
            "registry.api.get_passport", return_value=mock_passport
        ) as get_passport:
            with patch(
                "registry.api.validate_credential", side_effect=[[], []]
            ) as validate_credential:
                client = Client()
                return client.post(
                    "/registry/submit-passport",
                    json.dumps(
                        {
                            "community": scorer_community_with_binary_scorer.id,
                            "address": "0x0123",
                        }
                    ),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
                )


@then('the score "0.000000000" is returned')
def _(scoreResponseFor0):
    """the score "0.000000000" is returned."""
    assert scoreResponseFor0.json()[0]["score"] == "0.000000000"


###################################################################################################


@scenario("features/choose_binary_scorer.feature", 'Get score of "1.000000000"')
def test_get_score_of_1000000000():
    """Get score of "1.000000000"."""


@when(
    "I submit a passport that yields a weighted score greater or equal than the threshold",
    target_fixture="scoreResponseFor1",
)
def _(scorer_community_with_binary_scorer, scorer_api_key):
    """I submit a passport that yields a weighted score greater or equal than the threshold."""
    print("-" * 30)
    print(scorer_community_with_binary_scorer.scorer.binaryweightedscorer)
    print("-" * 30)
    with patch(
        "scorer_weighted.computation.calculate_weighted_score",
        return_value=[Decimal("90")],
    ) as calculate_weighted_score:
        with patch(
            "registry.api.get_passport", return_value=mock_passport
        ) as get_passport:
            with patch(
                "registry.api.validate_credential", side_effect=[[], []]
            ) as validate_credential:
                client = Client()
                return client.post(
                    "/registry/submit-passport",
                    json.dumps(
                        {
                            "community": scorer_community_with_binary_scorer.id,
                            "address": "0x0123",
                        }
                    ),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
                )


@then('the score "1.000000000" is returned')
def _(scoreResponseFor1):
    """the score "1.000000000" is returned."""
    assert scoreResponseFor1.json()[0]["score"] == "1.000000000"
