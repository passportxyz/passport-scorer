# pylint: disable=unused-import
import pytest

from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from scorer.test.conftest import (
    access_token,
    scorer_account,
    scorer_community,
    scorer_user,
)


@pytest.fixture
def weight_config():
    config = WeightConfiguration.objects.create(
        version="v1",
        threshold=5.0,
        active=True,
        description="Test",
    )

    for provider, weight in GITCOIN_PASSPORT_WEIGHTS.items():
        WeightConfigurationItem.objects.create(
            weight_configuration=config,
            provider=provider,
            weight=float(weight),
        )

    return config
