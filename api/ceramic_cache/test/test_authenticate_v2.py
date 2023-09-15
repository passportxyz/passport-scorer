import pytest
from ceramic_cache.test.test_authenticate_v1 import TestAuthenticate

pytestmark = pytest.mark.django_db


class TestAuthenticateV2(TestAuthenticate):
    """
    We just inherit all tests from v1 for v2, there is no change
    """

    base_url = "/ceramic-cache/v2"
