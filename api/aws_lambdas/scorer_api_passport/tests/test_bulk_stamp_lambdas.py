import json
from decimal import Decimal

import pytest
from django.conf import settings

from aws_lambdas.scorer_api_passport.v1.stamps import bulk_DELETE, bulk_PATCH, bulk_POST
from ceramic_cache.models import CeramicCache

from .helpers import MockContext, address, good_stamp, headers

pytestmark = pytest.mark.django_db


def test_patch(
    scorer_community_with_binary_scorer,
    mocker,
    mock_authentication,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk
    event = {
        "headers": headers,
        "body": json.dumps(
            [
                good_stamp,
                {"provider": "Ens"},
            ]
        ),
        "isBase64Encoded": False,
    }
    context = MockContext()

    mocker.patch(
        "registry.atasks.avalidate_credentials",
        side_effect=lambda _, passport_data: passport_data,
    )

    response = bulk_PATCH._handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["stamps"][0]["provider"] == "Google"
    assert Decimal(body["score"]["score"]) > Decimal(0)
    assert Decimal(body["score"]["threshold"]) > Decimal(0)
    assert body["success"] is True


def test_delete(
    scorer_community_with_binary_scorer,
    mocker,
    mock_authentication,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk
    CeramicCache.objects.create(
        address=address, provider="Google", type=CeramicCache.StampType.V1
    ).save()

    event = {
        "headers": headers,
        "body": json.dumps([{"provider": "Google"}]),
        "isBase64Encoded": False,
    }
    context = MockContext()

    mocker.patch(
        "registry.atasks.avalidate_credentials",
        side_effect=lambda _, passport_data: passport_data,
    )

    response = bulk_DELETE._handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert len(body["stamps"]) == 0
    assert Decimal(body["score"]["score"]) == Decimal(0)
    assert Decimal(body["score"]["threshold"]) > Decimal(0)
    assert body["success"] is True


def test_post(
    scorer_community_with_binary_scorer,
    mocker,
    mock_authentication,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk
    event = {
        "headers": headers,
        "body": json.dumps(
            [
                good_stamp,
            ]
        ),
        "isBase64Encoded": False,
    }
    context = MockContext()

    mocker.patch(
        "registry.atasks.avalidate_credentials",
        side_effect=lambda _, passport_data: passport_data,
    )

    response = bulk_POST._handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 201
    assert body["stamps"][0]["provider"] == "Google"
    assert Decimal(body["score"]["score"]) > Decimal(0)
    assert Decimal(body["score"]["threshold"]) > Decimal(0)
    assert body["success"] is True
