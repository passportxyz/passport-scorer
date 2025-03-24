from datetime import datetime, timedelta, timezone

import pytest
from django.conf import settings

from scorer.test.conftest import (
    api_key,  # noqa
    sample_address,  # noqa
    sample_provider,  # noqa
    sample_token,  # noqa
    scorer_account,  # noqa
    scorer_community,  # noqa
    scorer_community_with_binary_scorer,  # noqa
    scorer_passport,  # noqa
    scorer_user,  # noqa
    ui_scorer,  # noqa
    verifiable_credential,  # noqa
    weight_config,  # noqa
)


@pytest.fixture
def sample_addresses():
    return ["0x123", "0x456", "0x789"]


@pytest.fixture
def sample_providers():
    return ["Twitter", "Github", "LinkedIn"]


@pytest.fixture
def sample_expiration_dates(sample_providers):
    now = datetime.now(timezone.utc)
    return [now + timedelta(days=idx) for idx, _ in enumerate(sample_providers, 1)]


@pytest.fixture
def sample_stamps(sample_expiration_dates, sample_providers, sample_address):
    return [
        {
            "type": ["VerifiableCredential"],
            "credentialSubject": {
                "id": sample_address,
                "hash": "v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
                "provider": sample_providers[idx],
            },
            "issuer": settings.TRUSTED_IAM_ISSUERS[0],
            "issuanceDate": (expiration_date - timedelta(days=30)).isoformat(),
            "expirationDate": expiration_date.isoformat(),
            "proof": {
                "proofValue": "proof-v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
            },
        }
        for idx, expiration_date in enumerate(sample_expiration_dates)
    ]


def pytest_configure():
    settings.CERAMIC_CACHE_SCORER_ID = "1"
