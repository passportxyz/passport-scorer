"""Create Community ID feature tests."""

from decimal import Decimal
import json

import pytest
from account.models import Community
from account.test.test_community import mock_community_body
from django.test import Client
from ninja_jwt.schema import RefreshToken
from pytest_bdd import given, scenario, then, when
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

pytestmark = pytest.mark.django_db


@scenario("features/create_community_id.feature", "Successfully create a Community ID")
def test_successfully_create_a_community_id():
    """Successfully create a Community ID."""


@given("that I have an API account", target_fixture="account")
def _(scorer_account, mocker):
    """that I have an API account."""
    pass


@when(
    "I enter a name for this Community that is unique among the Community registered under my account",
    target_fixture="community_response",
)
def _(scorer_user):
    """I enter a name for this Community that is unique among the Community registered under my account."""
    refresh = RefreshToken.for_user(scorer_user)
    access_token = refresh.access_token

    client = Client()
    community_response = client.post(
        "/account/communities",
        json.dumps(mock_community_body),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    return community_response


@when("I hit the Add Community button")
def _():
    """I hit the Add Community button."""
    # Implemented in previous step
    pass


@then("that Community is registered")
def _(community_response):
    """that Community is registered."""
    assert community_response.status_code == 200
    assert len(Community.objects.all()) == 1
    community = Community.objects.all()[0]
    assert community.name == "test"
    assert community.description == "test"


@then("that Community uses the latest weights and threshold")
def _():
    """that Community uses the latest weights and threshold."""
    community = Community.objects.all()[0]
    scorer = community.scorer.binaryweightedscorer
    assert scorer.threshold == Decimal("21.11")
    assert scorer.weights["ETHGasSpent.5"] == "1.57425115793055"
