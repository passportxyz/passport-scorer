from datetime import datetime, timedelta

import pytest

import api_logging as logging
from account.models import Nonce, tz

pytestmark = pytest.mark.django_db

log = logging.getLogger(__name__)


def test_nonce_validation():
    """Make sure a nonce is properly validate:
    - validation is successfull if nonce was not used
    - if properly validated nonce is marked as used, and cannot be used a second time
    """
    nonce = Nonce.create_nonce()

    assert Nonce.validate_nonce(nonce.nonce)
    # Use the nonce once
    assert Nonce.use_nonce(nonce.nonce) is True

    # Test that nonce validation throws when attempted to be validate after use
    with pytest.raises(Nonce.DoesNotExist):
        Nonce.validate_nonce(nonce.nonce)

    # Test that nonce cannot be used  asecond time
    assert Nonce.use_nonce(nonce.nonce) is False


def test_nonce_expiration():
    validNonce = Nonce.create_nonce(ttl=10)
    expiredNonce = Nonce.create_nonce(ttl=-10)

    assert Nonce.use_nonce(expiredNonce.nonce) is False
    assert Nonce.use_nonce(validNonce.nonce) is True
