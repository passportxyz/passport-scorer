import pytest
from django.db import IntegrityError

from registry.models import HashScorerLink

pytestmark = pytest.mark.django_db


def test_uniqueness_constraint():
    HashScorerLink.objects.create(
        community_id=1,
        hash="hash1",
        address="0x123",
        expires_at="2099-01-01 00:00:00+00:00",
    )

    with pytest.raises(IntegrityError):
        HashScorerLink.objects.create(
            community_id=1,
            hash="hash1",
            address="0x456",
            expires_at="2099-01-02 00:00:00+00:00",
        )
