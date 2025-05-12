"""Submit address for passport feature tests."""

import json
from decimal import Decimal

import pytest
from django.test import Client
from eth_account.messages import encode_defunct
from pytest_bdd import given, scenario, then, when
from web3 import Web3

from account.models import Nonce
from registry.test.test_passport_submission import (
    mock_passport,
    mock_passport_expiration_date,
    mock_utc_timestamp,
)
from registry.utils import get_signing_message

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

pytestmark = pytest.mark.django_db

####################################################################################
# Scenario: Submit passport successfully
####################################################################################


@scenario("features/submit_passport.feature", "Submit passport successfully")
def test_submit_passport_successfully():
    """Submit passport successfully."""


@given(
    "that I'm a Passport developer and have a community ID", target_fixture="community"
)
def _(scorer_community_with_gitcoin_default):
    """that I'm a Passport developer and have a community ID."""
    pass


@when(
    "I call the `/registry/submit-passport` API for an Ethereum account and a community ID",
    target_fixture="submit_passport_response",
)
def submit_passport(scorer_api_key, scorer_community_with_gitcoin_default, mocker):
    """I call the `/registry/submit-passport` API for an Ethereum account and a community ID"""

    mocker.patch("registry.atasks.aget_passport", return_value=mock_passport)
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], []])
    mocker.patch("registry.atasks.get_utc_time", return_value=mock_utc_timestamp)
    client = Client()

    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    nonce = Nonce.create_nonce().nonce
    signing_message = get_signing_message(nonce)

    signed_message = web3.eth.account.sign_message(
        encode_defunct(text=signing_message),
        private_key=web3_account.key,
    )

    payload = {
        "community": scorer_community_with_gitcoin_default.id,
        "address": scorer_community_with_gitcoin_default.account.address,
        "signature": signed_message.signature.hex(),
        "nonce": nonce,
    }

    submit_response = client.post(
        "/registry/submit-passport",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
    )

    return submit_response


@given(
    "that I have submitted a passport for scoring using the api",
    target_fixture="submit_passport_response",
)
def _(scorer_api_key, scorer_community_with_gitcoin_default, mocker):
    """that I have submitted a passport for scoring using the api."""
    return submit_passport(
        scorer_api_key, scorer_community_with_gitcoin_default, mocker
    )


@then("I receive back the score details with status `PROCESSING`")
def _(scorer_community_with_gitcoin_default, submit_passport_response):
    """I receive back the score details with status `PROCESSING`."""
    # TODO change PROCESSING => DONE above
    returned_json = submit_passport_response.json()
    returned_json["score"] = Decimal(returned_json["score"])

    assert returned_json == {
        "address": scorer_community_with_gitcoin_default.account.address.lower(),
        "score": Decimal("0.733000000"),
        "status": "DONE",
        "last_score_timestamp": mock_utc_timestamp.isoformat(),
        "expiration_date": mock_passport_expiration_date.isoformat(),
        "evidence": None,
        "error": None,
        "stamp_scores": {
            "Ens": 0.208,
            "Google": 0.525,
        },
    }


@given("the scoring of the passport has finished successfully")
def _(scorer_community_with_gitcoin_default, mocker):
    """the scoring of the passport has finished successfully."""
    mocker.patch("registry.atasks.aget_passport", return_value=mock_passport)
    mocker.patch("registry.atasks.get_utc_time", return_value=mock_utc_timestamp)
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], []])
    # execute the task
    # score_passport(
    #     scorer_community_with_gitcoin_default.id,
    #     scorer_community_with_gitcoin_default.account.address,
    # )


@when(
    "I call the `/registry/score` API for an Ethereum account and a community ID",
    target_fixture="score_response",
)
def _(scorer_api_key, scorer_community_with_gitcoin_default):
    """I call the `/registry/score` API for an Ethereum account and a community ID."""
    client = Client()

    response = client.get(
        f"/registry/score/{scorer_community_with_gitcoin_default.id}/{scorer_community_with_gitcoin_default.account.address}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
    )

    return response


@when("I call the submit-passport API for an Ethereum account under that community ID")
def _(scorer_api_key, scorer_community_with_gitcoin_default, mocker):
    """I call the submit-passport API for an Ethereum account under that community ID."""
    submit_passport(scorer_api_key, scorer_community_with_gitcoin_default, mocker)


####################################################################################
# Scenario: Scoring succeeded
####################################################################################
@scenario("features/submit_passport.feature", "Scoring succeeded")
def test_scoring_succeeded():
    """Scoring succeeded."""


@then("I receive back the score details with status `DONE`")
def _(scorer_community_with_gitcoin_default, score_response):
    """I receive back the score details with status `DONE`."""
    assert score_response.status_code == 200

    assert score_response.json() == {
        "address": scorer_community_with_gitcoin_default.account.address.lower(),
        "score": "0.733000000",
        "status": "DONE",
        "last_score_timestamp": mock_utc_timestamp.isoformat(),
        "expiration_date": mock_passport_expiration_date.isoformat(),
        "evidence": None,
        "error": None,
        "stamp_scores": {
            "Ens": 0.208,
            "Google": 0.525,
        },
    }


####################################################################################
# Scenario: Scoring failed
####################################################################################
@scenario("features/submit_passport.feature", "Scoring failed")
def test_scoring_failed():
    """Scoring failed."""


@given(
    "the scoring of the passport has failed",
    target_fixture="scoring_failed_score_response",
)
def _(scorer_api_key, scorer_community_with_gitcoin_default, mocker):
    """the scoring of the passport has failed."""
    mocker.patch(
        "registry.atasks.aget_passport", side_effect=Exception("something bad")
    )
    mocker.patch("registry.atasks.get_utc_time", return_value=mock_utc_timestamp)
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], []])

    payload = {
        "scorer_id": str(scorer_community_with_gitcoin_default.id),
        "address": scorer_community_with_gitcoin_default.account.address,
    }

    client = Client()
    response = client.post(
        "/registry/submit-passport",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
    )

    assert response.status_code == 200
    # score_passport(
    #     scorer_community_with_gitcoin_default.id,
    #     scorer_community_with_gitcoin_default.account.address,
    # )

    return response


@then("I receive back the score details with status `ERROR`")
def _(scorer_community_with_gitcoin_default, scoring_failed_score_response):
    """I receive back the score details with status `ERROR`."""
    assert scoring_failed_score_response.json() == {
        "address": scorer_community_with_gitcoin_default.account.address.lower(),
        "score": None,
        "status": "ERROR",
        "last_score_timestamp": None,
        "expiration_date": None,
        "evidence": None,
        "error": "something bad",
        "stamp_scores": {
            "Ens": 0.208,
            "Google": 0.525,
        },
    }


####################################################################################
# Scenario: Scoring is in progress
####################################################################################
@scenario("features/submit_passport.feature", "Scoring is in progress")
def test_scoring_is_in_progress():
    """Scoring is in progress."""


@given("And the scoring of the passport is still in progress")
def _():
    """And the scoring of the passport is still in progress."""
    pass


@then(
    "I receive back the score details with status `PROCESSING` while the scoring is still in progress"
)
def _(scorer_community_with_gitcoin_default, score_response, mocker):
    """I receive back the score details with status `PROCESSING` while the scoring is still in progress."""
    assert score_response.status_code == 200
    mocker.patch("registry.atasks.get_utc_time", return_value=mock_utc_timestamp)

    response_data = score_response.json()

    ################################################################################
    # Because we have moved to an async func, scoring should not be in "PROCESSING" any more
    # but directly in "DONE"
    ################################################################################
    assert (
        response_data["address"]
        == scorer_community_with_gitcoin_default.account.address.lower()
    )
    assert response_data["score"] == "0.733000000"
    assert response_data["status"] == "DONE"
    assert response_data["last_score_timestamp"] == mock_utc_timestamp.isoformat()
    assert response_data["evidence"] is None
    assert response_data["error"] is None


####################################################################################
# Scenario: Reset error if scoring succeeded after an initial error.
####################################################################################


@scenario(
    "features/submit_passport.feature",
    "Reset error if scoring succeeded after an initial error",
)
def test_reset_error_if_scoring_succeeded_after_an_initial_error():
    """Reset error if scoring succeeded after an initial error."""


@given("I have submitted the passport for scoring a second time")
def _(scorer_api_key, scorer_community_with_gitcoin_default, mocker):
    """I have submitted the passport for scoring a second time."""
    return submit_passport(
        scorer_api_key, scorer_community_with_gitcoin_default, mocker
    )


@then("the previous error message has been reset to None")
def _(score_response):
    """the previous error message has been reset to None."""
    assert score_response.json()["error"] is None


####################################################################################
# Scenario: As a developer, I want to rely on the Gitcoin Community Scorer scoring settings of the API
####################################################################################


@scenario(
    "features/submit_passport.feature",
    "As a developer, I want to rely on the Gitcoin Community Scorer scoring settings of the API",
)
def test_as_a_developer_i_want_to_rely_on_the_gitcoin_community_scorer_scoring_settings_of_the_api():
    """As a developer, I want to rely on the Gitcoin Community Scorer scoring settings of the API."""
    pass


@given("I have not further configured its settings")
def _():
    """I have not further configured its settings."""
    # Nothingg to do here
    pass


@given("that I have created a community ID")
def _(scorer_community_with_gitcoin_default):
    """that I have created a community ID."""
    pass


@then(
    "I want to get a score based on the Gitcoin Community Score and deduplication rules (see default deduplication settings here)"
)
def _(scorer_community_with_gitcoin_default, score_response):
    """I want to get a score based on the Gitcoin Community Score and deduplication rules (see default deduplication settings here)."""

    assert score_response.status_code == 200
    score_response_data = score_response.json()
    assert score_response_data == {
        "address": scorer_community_with_gitcoin_default.account.address.lower(),
        "score": "0.733000000",
        "status": "DONE",
        "last_score_timestamp": mock_utc_timestamp.isoformat(),
        "expiration_date": mock_passport_expiration_date.isoformat(),
        "evidence": None,
        "error": None,
        "stamp_scores": {
            "Ens": 0.208,
            "Google": 0.525,
        },
    }


def test_invalid_address(scorer_api_key, scorer_community_with_gitcoin_default):
    payload = {
        "community": scorer_community_with_gitcoin_default.id,
        "address": scorer_community_with_gitcoin_default.account.address + "q",
    }

    client = Client()
    submit_response = client.post(
        "/registry/submit-passport",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
    )

    assert submit_response.status_code == 400
