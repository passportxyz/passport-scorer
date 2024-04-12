import json

import pytest
from aws_lambdas.scorer_api_passport.v1 import (
    score_GET,
    score_POST,
    stamp_GET,
    weights_GET,
)
from ceramic_cache.models import CeramicCache
from django.conf import settings
from registry.models import Passport, Score
from registry.utils import get_utc_time

from .helpers import MockContext, address, headers

pytestmark = pytest.mark.django_db


def test_score_get(
    scorer_community_with_binary_scorer,
    mock_authentication,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk

    passport = Passport.objects.create(
        address=address,
        community=scorer_community_with_binary_scorer,
    )
    Score.objects.create(
        passport=passport,
        score=1,
        status=Score.Status.DONE,
        last_score_timestamp=get_utc_time(),
        error=None,
        stamp_scores=[],
        evidence={
            "rawScore": 10,
            "type": "binary",
            "success": True,
            "threshold": 5,
        },
    )

    event = {
        "headers": headers,
        "isBase64Encoded": False,
    }
    context = MockContext()

    response = score_GET._handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["evidence"]["rawScore"] == 10


def test_score_post(
    scorer_community_with_binary_scorer,
    mock_authentication,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk

    event = {
        "headers": headers,
        "isBase64Encoded": False,
    }

    context = MockContext()

    assert Score.objects.count() == 0

    response = score_POST._handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["score"] == "0"
    assert Score.objects.count() == 1


def test_stamp_get(
    scorer_community_with_binary_scorer,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk

    CeramicCache.objects.create(
        address=address, provider="Google", type=CeramicCache.StampType.V1
    )

    event = {
        "queryStringParameters": {
            "address": address,
        },
        "isBase64Encoded": False,
    }

    context = MockContext()

    response = stamp_GET._handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["stamps"][0]["provider"] == "Google"


def test_weights_get():
    event = {
        "isBase64Encoded": False,
    }

    context = MockContext()

    response = weights_GET._handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert len(body) > 0
