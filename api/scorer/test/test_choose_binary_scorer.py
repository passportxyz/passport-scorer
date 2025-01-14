"""Select Binary Scorer feature tests."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client
from pytest_bdd import given, scenario, then, when

from account.models import Community
from registry.tasks import score_passport
from registry.test.test_passport_submission import mock_passport, mock_utc_timestamp
from registry.weight_models import WeightConfiguration
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
def scorers_put_response(access_token, scorer_community_with_binary_scorer):
    scorer = scorer_community_with_binary_scorer.scorer
    client = Client()
    return client.put(
        f"/account/communities/{scorer_community_with_binary_scorer.id}/scorers",
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
def _(scorer_community_with_binary_scorer):
    scorer = Community.objects.get(id=scorer_community_with_binary_scorer.id).scorer

    scorer.binaryweightedscorer.threshold = 0.9
    scorer.binaryweightedscorer.save()
    assert scorer.type == "WEIGHTED_BINARY"
    assert scorer.binaryweightedscorer
    assert type(scorer.binaryweightedscorer) == BinaryWeightedScorer


@when("I choose to score a passport", target_fixture="scoreResponse")
def score_response(scorer_community_with_binary_scorer, scorer_api_key):
    """I choose to score a passport."""
    with patch("registry.atasks.aget_passport", return_value=mock_passport):
        with patch("registry.atasks.validate_credential", side_effect=[[], []]):
            client = Client()
            submitResponse = client.post(
                "/registry/submit-passport",
                json.dumps(
                    {
                        "community": scorer_community_with_binary_scorer.id,
                        "address": "0x71Ad3e3057Ca74967239C66ca6D3A9C2A43a58fC",
                    }
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
            )

            response = submitResponse.json()
            # read the score ...
            assert response["status"] == "DONE"
            assert response["address"] == "0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc"
            assert Decimal(response["score"]) == Decimal("1.000000000")
            return client.get(
                f"/registry/score/{scorer_community_with_binary_scorer.id}/0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
            )


@then("the binary score should be returned")
def _(scoreResponse):
    """the binary score should be returned."""
    scoreResponseData = scoreResponse.json()
    print("scoreResponseData", scoreResponseData)
    assert scoreResponseData["address"] == "0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc"
    assert scoreResponseData["status"] == "DONE"
    assert scoreResponseData["score"] == "1.000000000"
    assert scoreResponseData["evidence"]["type"] == "ThresholdScoreCheck"
    assert scoreResponseData["evidence"]["success"] is True

    last_score_timestamp = datetime.fromisoformat(
        scoreResponseData["last_score_timestamp"]
    )
    assert (
        datetime.now(timezone.utc) - last_score_timestamp
    ).seconds < 5  # The timestamp should be recent


@then("the raw score should be returned")
def _(scoreResponse):
    """the raw score should be returned."""
    assert float(scoreResponse.json()["evidence"]["rawScore"]) > 0


@then("the threshold should be returned")
def _(scoreResponse):
    """the threshold should be returned."""
    assert (
        scoreResponse.json()["evidence"]["threshold"] == 0.9
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
    scorer = Community.objects.get(id=scorer_community_with_binary_scorer.id).scorer

    scorer.binaryweightedscorer.threshold = 75
    scorer.binaryweightedscorer.save()

    with patch(
        "scorer_weighted.computation.acalculate_weighted_score",
        return_value=[
            {
                "sum_of_weights": Decimal("70"),
                "earned_points": {},
                "expiration_date": datetime.now(timezone.utc),
                "stamp_expiration_dates": {},
            }
        ],
    ):
        with patch("registry.atasks.aget_passport", return_value=mock_passport):
            with patch("registry.atasks.validate_credential", side_effect=[[], []]):
                client = Client()
                submitResponse = client.post(
                    "/registry/submit-passport",
                    json.dumps(
                        {
                            "community": scorer_community_with_binary_scorer.id,
                            "address": "0x71Ad3e3057Ca74967239C66ca6D3A9C2A43a58fC",
                        }
                    ),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
                )

            # execute the task
            score_passport(
                scorer_community_with_binary_scorer.id,
                "0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc",
            )
            # read the score ...
            response = submitResponse.json()
            # read the score ...
            assert response["status"] == "DONE"
            assert response["address"] == "0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc"
            assert Decimal(response["score"]) == Decimal("0E-9")

            return client.get(
                f"/registry/score/{scorer_community_with_binary_scorer.id}/0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
            )


@then('the score "0.000000000" is returned')
def _(scoreResponseFor0):
    """the score "0.000000000" is returned."""
    assert scoreResponseFor0.json()["score"] == "0E-9"


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

    scorer = Community.objects.get(id=scorer_community_with_binary_scorer.id).scorer

    scorer.binaryweightedscorer.threshold = 75
    scorer.binaryweightedscorer.save()

    with patch("registry.atasks.get_utc_time", return_value=mock_utc_timestamp):
        with patch(
            "scorer_weighted.computation.acalculate_weighted_score",
            return_value=[
                {
                    "sum_of_weights": Decimal("90"),
                    "earned_points": {},
                    "expiration_date": datetime.now(timezone.utc),
                    "stamp_expiration_dates": {},
                }
            ],
        ):
            with patch("registry.atasks.aget_passport", return_value=mock_passport):
                with patch("registry.atasks.validate_credential", side_effect=[[], []]):
                    client = Client()
                    submit_response = client.post(
                        "/registry/submit-passport",
                        json.dumps(
                            {
                                "community": scorer_community_with_binary_scorer.id,
                                "address": "0x71Ad3e3057Ca74967239C66ca6D3A9C2A43a58fC",
                            }
                        ),
                        content_type="application/json",
                        HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
                    )

                    # read the score ...
                    submit_response_data = submit_response.json()

                    assert (
                        submit_response_data["address"]
                        == "0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc"
                    )
                    assert Decimal(submit_response_data["score"]) == Decimal(1)
                    assert submit_response_data["status"] == "DONE"
                    assert (
                        submit_response_data["last_score_timestamp"]
                        == mock_utc_timestamp.isoformat()
                    )
                    assert submit_response_data["evidence"] == {
                        "rawScore": 90.0,
                        "success": True,
                        "threshold": 75.0,
                        "type": "ThresholdScoreCheck",
                    }
                    assert submit_response_data["error"] is None

                    return client.get(
                        f"/registry/score/{scorer_community_with_binary_scorer.id}/0x71Ad3e3057Ca74967239C66ca6D3A9C2A43a58fC",
                        content_type="application/json",
                        HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
                    )


@then('the score "1.000000000" is returned')
def _(scoreResponseFor1):
    """the score "1.000000000" is returned."""
    score_response_data = scoreResponseFor1.json()
    assert (
        score_response_data["address"] == "0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc"
    )
    assert Decimal(score_response_data["score"]) == Decimal(1)
    assert score_response_data["status"] == "DONE"
    assert score_response_data["last_score_timestamp"] == mock_utc_timestamp.isoformat()
    assert score_response_data["evidence"] == {
        "rawScore": 90.0,
        "success": True,
        "threshold": 75.0,
        "type": "ThresholdScoreCheck",
    }
    assert score_response_data["error"] is None
