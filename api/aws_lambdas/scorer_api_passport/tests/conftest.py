import pytest
from scorer.test.conftest import (
    passport_holder_addresses,
    scorer_account,
    scorer_api_key,
    scorer_community_with_binary_scorer,
    scorer_user,
)

from .helpers import address


@pytest.fixture
def mock_authentication(mocker):
    mocker.patch(
        "aws_lambdas.scorer_api_passport.utils.auth.get_validated_token",
        side_effect=lambda x: {"did": "key:" + address},
    )
