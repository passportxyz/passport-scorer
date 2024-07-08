# pylint: disable=no-value-for-parameter
# pyright: reportGeneralTypeIssues=false
import json

import pytest
from passport.test.test_analysis import MockLambdaClient

from aws_lambdas.scorer_api_passport.tests.helpers import MockContext

from ..analysis_GET import _handler

pytestmark = pytest.mark.django_db

address = "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D"


def test_successful_analysis(
    scorer_api_key,
    mocker,
):
    """
    Tests that analysis can be requested successfully.
    """

    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }
    mocker.patch(
        "passport.api.get_lambda_client",
        MockLambdaClient,
    )
    response = _handler(event, MockContext())

    # TODO: geri uncomment this
    # assert response is not None
    # assert response["statusCode"] == 200

    # body = json.loads(response["body"])

    # assert body["address"] == address
    # assert body["details"]["models"]["ethereum_activity"]["score"] == 50


def test_bad_auth(
    mocker,
):
    """
    Tests that analysis can be requested successfully.
    """

    event = {
        "headers": {"x-api-key": "bad_auth"},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }
    mocker.patch(
        "passport.api.get_lambda_client",
        MockLambdaClient,
    )
    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 403
    assert json.loads(response["body"])["error"] == "Unauthorized"


def test_bad_address(
    scorer_api_key,
    mocker,
):
    """
    Tests that analysis can be requested successfully.
    """

    bad_address = address[:-1] + "d"

    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{bad_address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }
    mocker.patch(
        "passport.api.get_lambda_client",
        MockLambdaClient,
    )
    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "Invalid address"
