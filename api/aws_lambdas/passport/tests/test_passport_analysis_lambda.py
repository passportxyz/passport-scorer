# pylint: disable=no-value-for-parameter
# pyright: reportGeneralTypeIssues=false
import copy
import json

import pytest
from django.conf import settings

import aws_lambdas.passport.analysis_GET
from aws_lambdas.passport.analysis_GET import _handler
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext

pytestmark = pytest.mark.django_db

address = "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D"


mock_model_responses = {
    "ethereum_activity": {
        "status": 200,
        "data": {
            "human_probability": 75,
            "n_transactions": 10,
            "first_funder": "funder",
            "first_funder_amount": 1000,
        },
        "metadata": {"model_name": "ethereum_activity", "version": "1.0"},
    },
    "nft": {
        "status": 200,
        "data": {
            "human_probability": 85,
            "n_transactions": 10,
            "first_funder": "funder",
            "first_funder_amount": 1000,
        },
        "metadata": {"model_name": "social_media", "version": "2.0"},
    },
    "zksync": {
        "status": 200,
        "data": {
            "human_probability": 95,
            "n_transactions": 10,
            "first_funder": "funder",
            "first_funder_amount": 1000,
        },
        "metadata": {"model_name": "transaction_history", "version": "1.5"},
    },
    "aggregate": {
        "status": 200,
        "data": {
            "human_probability": 90,
            "n_transactions": 10,
            "first_funder": "funder",
            "first_funder_amount": 1000,
        },
        "metadata": {"model_name": "aggregate", "version": "2.5"},
    },
}


def mock_post_response(session, url, data):
    # Determine which model is being requested

    for model, endpoint in settings.MODEL_ENDPOINTS.items():
        if endpoint in url:
            response_data = mock_model_responses.get(
                model,
                {
                    "status": 200,
                    "data": {
                        "human_probability": 0,
                        "n_transactions": 10,
                        "first_funder": "funder",
                        "first_funder_amount": 1000,
                    },
                },
            )
            break
    else:
        response_data = {"error": "Unknown model"}

    return response_data


def mock_post_response_with_failure(fail_for_model):
    def mock_response(session, url, data):
        for model, endpoint in settings.MODEL_ENDPOINTS.items():
            if endpoint in url:
                response_data = dict(
                    **mock_model_responses.get(
                        model,
                        {
                            "status": 200,
                            "data": {
                                "human_probability": 0,
                                "n_transactions": 10,
                                "first_funder": "funder",
                                "first_funder_amount": 1000,
                            },
                        },
                    )
                )

                # include error http status error if failure is
                # expected to be mocked
                print("*" * 40)
                print(model, fail_for_model)
                print("*" * 40)
                if model == fail_for_model:
                    response_data = copy.deepcopy(response_data)
                    response_data["status"] = 500
                break
        else:
            response_data = {"error": "Unknown model"}

        return response_data

    return mock_response


def test_successful_analysis_eth(
    scorer_api_key,
    mocker,
):
    """
    Tests that analysis can be requested successfully.
    """

    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {"model_list": "ethereum_activity"},
        "isBase64Encoded": False,
    }
    with mocker.patch("passport.api.fetch", side_effect=mock_post_response):
        response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 200

    body = json.loads(response["body"])

    assert body["address"] == address
    assert body["details"]["models"]["ethereum_activity"]["score"] == 75


def test_bad_auth(
    mocker,
):
    """
    Tests that error is thrown if auth is bad
    """

    event = {
        "headers": {"x-api-key": "bad_auth"},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }

    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 401
    assert json.loads(response["body"])["error"] == "Invalid API Key."


def test_bad_address(
    scorer_api_key,
    mocker,
):
    """
    Tests that error is thrown is addrss is bad
    """

    bad_address = address[:-1] + "d"

    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{bad_address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }
    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "Invalid address."


def test_bad_model(
    scorer_api_key,
    mocker,
):
    """
    Tests that error is thrown if unsupported model is requested
    """

    model = "bad_model"
    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {"model_list": model},
        "isBase64Encoded": False,
    }

    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 400
    assert (
        json.loads(response["body"])["error"]
        == f"Invalid model name(s): {', '.join([model])}. Must be one of {', '.join(settings.MODEL_ENDPOINTS.keys())}"
    )


def test_analysis_eth_unqoute_model_list(
    scorer_api_key,
    mocker,
):
    """
    Tests that the model_list in the aws_lambda function is urlunquoted
    """

    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {"model_list": "ethereum_activity%2C%20zksync"},
        "isBase64Encoded": False,
    }
    spy = mocker.spy(aws_lambdas.passport.analysis_GET, "handle_get_analysis")
    response = _handler(event, MockContext())

    # Check that the model_list is unquoted properly
    spy.assert_called_with(address, "ethereum_activity, zksync")
