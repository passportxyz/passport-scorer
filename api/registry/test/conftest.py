import pytest

from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS

# pylint: disable=unused-import
from scorer.test.conftest import (
    gtc_staking_response,
    passport_holder_addresses,
    sample_address,
    scorer_account,
    scorer_api_key,
    scorer_api_key_no_permissions,
    scorer_community,
    scorer_community_with_binary_scorer,
    scorer_community_with_weighted_scorer,
    scorer_passport,
    scorer_score,
    scorer_user,
)


@pytest.fixture(autouse=True)
def weight_config(request):
    weights_to_use = getattr(request, "param", GITCOIN_PASSPORT_WEIGHTS)

    config = WeightConfiguration.objects.create(
        version="v1",
        threshold=5.0,
        active=True,
        description="Test",
    )

    for provider, weight in weights_to_use.items():
        WeightConfigurationItem.objects.create(
            weight_configuration=config,
            provider=provider,
            weight=float(weight),
        )

    return config
