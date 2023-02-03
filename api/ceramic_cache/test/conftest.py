from django.conf import settings
from scorer.test.conftest import (
    sample_address,
    sample_provider,
    verifiable_credential,
    sample_token,
)


def pytest_configure():
    try:
        settings.CERAMIC_CACHE_API_KEY = "supersecret"
    except:
        pass
