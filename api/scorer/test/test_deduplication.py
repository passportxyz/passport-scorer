"""Deduplication rules feature tests."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from django.test import Client
from eth_account.messages import encode_defunct
from pytest_bdd import given, scenario, then, when
from web3 import Web3

from account.models import Nonce
from registry.models import HashScorerLink, Passport, Stamp

# from registry.tasks import score_passport
from registry.test.test_passport_submission import (
    ens_credential,
    mock_passport,
    mock_utc_timestamp,
)
from registry.utils import get_signing_message

pytestmark = pytest.mark.django_db

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()


@scenario(
    "features/deduplication.feature",
    "As a developer, I want to rely on LIFO as a default stamp deduplication rule",
)
def test_as_a_developer_i_want_to_rely_on_lifo_as_a_default_stamp_deduplication_rule():
    """As a developer, I want to rely on LIFO as a default stamp deduplication rule."""


@given(
    "that a Passport holder submits a stamp with a hash that a different Passport holder previously submitted to the community",
    target_fixture="submit_passport_response",
)
def _(
    scorer_community_with_gitcoin_default,
    passport_holder_addresses,
    scorer_api_key,
    mocker,
):
    """that a Passport holder submits a stamp with a hash that a different Passport holder previously submitted to the community."""
    # Create the first passport + hashes
    first_passport = Passport.objects.create(
        address=passport_holder_addresses[0]["address"],
        community=scorer_community_with_gitcoin_default,
    )

    future_expiration_date = datetime.now(timezone.utc) + timedelta(days=15)

    Stamp.objects.create(
        passport=first_passport,
        provider="Some Provider",
        credential={},
    )

    HashScorerLink.objects.create(
        community=first_passport.community,
        hash="hash1",
        address=first_passport.address,
        expires_at=future_expiration_date,
    )

    # Create a stamp, with and ID that will be duplicate
    Stamp.objects.create(
        passport=first_passport,
        provider="Ens",
        credential={},
    )

    HashScorerLink.objects.create(
        community=first_passport.community,
        hash=ens_credential["credentialSubject"]["hash"],
        address=first_passport.address,
        expires_at=future_expiration_date,
    )

    # Now submit a second passport with the duplicate hash
    mocker.patch("registry.atasks.aget_passport", return_value=mock_passport)
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], []])
    client = Client()
    second_account = passport_holder_addresses[1]

    nonce = Nonce.create_nonce().nonce
    signing_message = get_signing_message(nonce)

    signed_message = web3.eth.account.sign_message(
        encode_defunct(text=signing_message),
        private_key=second_account["key"],
    )

    payload = {
        "community": scorer_community_with_gitcoin_default.id,
        "address": second_account["address"],
        "signature": signed_message.signature.hex(),
        "nonce": nonce,
    }

    submitResponse = client.post(
        "/registry/submit-passport",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
    )

    # execute the task
    # score_passport(
    #     scorer_community_with_gitcoin_default.id,
    #     passport_holder_addresses[1]["address"].lower(),
    # )

    # read the score ...
    response_data = submitResponse.json()

    assert response_data["address"] == passport_holder_addresses[1]["address"].lower()
    assert Decimal(response_data["score"]).quantize(Decimal("0.0000000001")) == Decimal(
        "0.5250000000"
    )
    assert response_data["status"] == "DONE"
    assert response_data["evidence"] is None
    assert response_data["error"] is None
    last_score_timestamp = datetime.fromisoformat(response_data["last_score_timestamp"])
    assert (
        datetime.now(timezone.utc) - last_score_timestamp
    ).seconds < 2  # The timestamp should be recent

    response = client.get(
        f"/registry/score/{scorer_community_with_gitcoin_default.id}/{passport_holder_addresses[1]['address'].lower()}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {scorer_api_key}",
    )

    # Return the response of reading back the score
    return response


@when(
    "we score the associated Passports, i.e., the Passports holding the stamps with identical hashes"
)
def _():
    """we score the associated Passports, i.e., the Passports holding the stamps with identical hashes."""
    pass


@then("score this Passport as if the stamp would be missing")
def _(passport_holder_addresses, submit_passport_response):
    """score this Passport as if the stamp would be missing."""
    # This means ignore the duplicate stamp in the passport that was just submitted
    assert submit_passport_response.status_code == 200
    submit_passport_response_data = submit_passport_response.json()

    assert (
        submit_passport_response_data["address"]
        == passport_holder_addresses[1]["address"].lower()
    )
    assert Decimal(submit_passport_response_data["score"]).quantize(
        Decimal("0.0000000001")
    ) == Decimal("0.5250000000")  # we expect a score only for the ENS stamp
    assert submit_passport_response_data["evidence"] is None
    last_score_timestamp = datetime.fromisoformat(
        submit_passport_response_data["last_score_timestamp"]
    )
    assert (
        datetime.now(timezone.utc) - last_score_timestamp
    ).seconds < 2  # The timestamp should be recent


@then(
    "we don't recognize the version of the stamp that has been more recently submitted"
)
def _():
    """we don't recognize the version of the stamp that has been more recently submitted."""
    # Covered in the previews step
    pass
