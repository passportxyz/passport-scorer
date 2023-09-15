import pytest
from ceramic_cache.models import CeramicCache
from ceramic_cache.test.test_get_stamps_v1 import TestGetStamp

pytestmark = pytest.mark.django_db


class TestGetStampV2(TestGetStamp):
    base_url = "/ceramic-cache/v2"
    stamp_version = CeramicCache.StampType.V2
