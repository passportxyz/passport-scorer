"""Retrieve logged Passport scores for Ethereum addresses within a community feature tests."""

import pytest
from django.test import Client
from pytest_bdd import given, scenario, then, when
from registry.models import Passport, Score

pytestmark = pytest.mark.django_db

client = Client()

limit = 2
offset = 0


@scenario(
    "features/retrieve_multiple_scores.feature",
    "Retrieve logged Passport scores for Ethereum addresses within a community",
)
def test_retrieve_logged_passport_scores_for_ethereum_addresses_within_a_community():
    """Retrieve logged Passport scores for Ethereum addresses within a community."""


@given("I have a community to which users have submitted passports")
def _(passport_holder_addresses, scorer_community):
    for holder in passport_holder_addresses:
        passport = Passport.objects.create(
            address=holder["address"],
            community=scorer_community,
        )

        score = Score.objects.create(
            passport=passport,
            score="1",
        )


@when(
    "I make a request calling /score/community/{community-id} API endpoint with my API Key",
    target_fixture="get_scores_response",
)
def _(passport_holder_addresses, scorer_community, scorer_api_key):
    """I make a request calling /score/community/{community-id} API endpoint with my API Key."""
    response = client.get(
        f"/registry/score/{scorer_community.id}?limit={limit}&offset={offset}",
        HTTP_AUTHORIZATION="Token " + scorer_api_key,
    )
    return response


@then("I get a paginated list of scores is returned for that community")
def _(get_scores_response, passport_holder_addresses):
    """I get a paginated list of scores is returned for that community."""
    assert get_scores_response.status_code == 200
    response_data = get_scores_response.json()
    assert response_data["count"] == 5

    assert (
        response_data["items"][0]["address"]
        == passport_holder_addresses[0]["address"].lower()
    )
