import pytest


@pytest.fixture(autouse=True)
def enable_v2_api(settings):
    settings.FF_V2_API = "on"
