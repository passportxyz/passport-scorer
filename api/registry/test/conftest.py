# pylint: disable=unused-import
import pytest
from account.models import AccountAPIKey
from registry.models import Passport, Score
from scorer.test.conftest import (
    passport_holder_addresses,
    scorer_account,
    scorer_community,
    scorer_user,
)


@pytest.fixture
def scorer_api_key(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account, name="Token for user 1"
    )
    return secret


@pytest.fixture
def scorer_passport(scorer_account, scorer_community):
    passport = Passport.objects.create(
        address=scorer_account.address,
        passport={"name": "John Doe"},
        community=scorer_community,
    )
    return passport


@pytest.fixture
def scorer_score(scorer_passport):
    stamp = Score.objects.create(
        passport=scorer_passport,
        score="0.650000000",
    )
    return stamp
