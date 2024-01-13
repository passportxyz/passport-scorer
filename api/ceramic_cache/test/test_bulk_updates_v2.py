import pytest
from ceramic_cache.models import CeramicCache
from ceramic_cache.test.test_bulk_updates_v1 import TestBulkStampUpdates

pytestmark = pytest.mark.django_db


class TestBulkStampUpdatesV2(TestBulkStampUpdates):
    base_url = "/ceramic-cache/v2"
    stamp_version = CeramicCache.StampType.V2
