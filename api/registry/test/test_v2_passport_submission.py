import pytest
from registry.test.test_passport_submission import ValidatePassportTestCase

pytestmark = pytest.mark.django_db


class ValidatePassportTestCaseV2(ValidatePassportTestCase):
    """
    We just inherit all tests from v1 for v2, there is no change
    """

    base_url = "/registry/v2"
