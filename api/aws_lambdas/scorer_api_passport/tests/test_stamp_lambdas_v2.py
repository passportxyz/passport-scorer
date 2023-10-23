import json

import pytest
from django.conf import settings

from aws_lambdas.scorer_api_passport.v2 import stamp_GET
from ceramic_cache.models import CeramicCache
from registry.models import Passport, Score
from registry.utils import get_utc_time

from .helpers import MockContext, address, headers

pytestmark = pytest.mark.django_db


def test_stamp_get(
    scorer_community_with_binary_scorer,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk

    CeramicCache.objects.create(
        address=address, provider="Google", type=CeramicCache.StampType.V2
    )

    event = {
        "queryStringParameters": {
            "address": address,
        },
        "isBase64Encoded": False,
    }

    context = MockContext()

    response = stamp_GET.handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["stamps"][0]["provider"] == "Google"
