import pytest


@pytest.fixture(autouse=True)
def enable_v2_api(settings):
    settings.FF_V2_API = "on"


@pytest.fixture(autouse=True)
def enable_multi_nullifier(settings):
    settings.FF_MULTI_NULLIFIER = "on"
