import pytest

from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from scorer.test.conftest import (
    passport_holder_addresses,
    scorer_account,
    scorer_api_key,
    scorer_community_with_binary_scorer,
    scorer_user,
    weight_config,
)

from .helpers import address


@pytest.fixture
def mock_authentication(mocker):
    mocker.patch(
        "aws_lambdas.scorer_api_passport.utils.auth.get_validated_token",
        side_effect=lambda x: {"did": "key:" + address},
    )
