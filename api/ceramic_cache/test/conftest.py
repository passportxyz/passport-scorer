import pytest
from django.conf import settings
from scorer.test.conftest import (
    api_key,  # noqa
    sample_address,  # noqa
    sample_provider,  # noqa
    sample_token,  # noqa
    scorer_account,  # noqa
    scorer_community,  # noqa
    scorer_passport,  # noqa
    scorer_community_with_binary_scorer,  # noqa
    scorer_user,  # noqa
    ui_scorer,  # noqa
    verifiable_credential,  # noqa
)


@pytest.fixture
def sample_addresses():
    return ["0x123", "0x456", "0x789"]


@pytest.fixture
def sample_providers():
    return ["Twitter", "Github", "LinkedIn"]


@pytest.fixture
def sample_stamps():
    return [
        {"stamp": 1},
        {"stamp": 2},
        {"stamp": 3},
    ]


def pytest_configure():
    settings.CERAMIC_CACHE_API_KEY = "supersecret"
    settings.CERAMIC_CACHE_SCORER_ID = ""
