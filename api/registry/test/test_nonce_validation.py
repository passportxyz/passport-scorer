import pytest
from account.models import Nonce

pytestmark = pytest.mark.django_db

import logging

log = logging.getLogger(__name__)


def test_nonce_validation():
    """Make sure a nonce is properly validate:
    - validation is successfull if nonce was not used
    - if properly validated nonce is marked as used, and cannot be used a second time
    """
    nonce = Nonce.create_nonce()

    assert Nonce.validate_nonce(nonce.nonce).id == nonce.id
    # Use the nonce once
    assert Nonce.use_nonce(nonce.nonce) == True

    # Test that nonce validation throws when attempted to be validate after use
    with pytest.raises(Nonce.DoesNotExist):
        Nonce.validate_nonce(nonce.nonce)

    # Test that nonce cannot be used  asecond time
    assert Nonce.use_nonce(nonce) == False
