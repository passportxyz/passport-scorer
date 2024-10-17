"""
Test module for the models score Lambda function.

This module contains tests for the AWS Lambda function that handles model scoring
requests. It includes tests for successful analysis, authentication, address validation,
and model validation.
"""

import json

import pytest
from django.conf import settings

import v2
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext
from v2.aws_lambdas.models_score_GET import _handler

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
    """
    Mock the POST response for different model endpoints.

    This function simulates the response from various model endpoints using
    the mock_model_responses dictionary. It determines which model is being
    requested based on the URL and returns the corresponding mock response.

    Args:
        session: The session object (not used in this mock function)
        url (str): The URL of the endpoint being called
        data: The data sent in the POST request (not used in this mock function)

    Returns:
        dict: A dictionary containing the mock response data for the requested model
    """
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
    """
    Create a mock response function that can simulate a failure for a specific model.

    This function returns another function that mocks POST responses, similar to
    mock_post_response, but allows simulating a failure (status 500) for a specified model.

    Args:
        fail_for_model (str): The name of the model for which to simulate a failure

    Returns:
        function: A mock response function that simulates responses with a potential failure
    """

    def mock_response(session, url, data):
        for model, endpoint in settings.MODEL_ENDPOINTS.items():
            if endpoint in url:
                response_data = {
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
                }

                if model == fail_for_model:
                    response_data = response_data.copy()
                    response_data["status"] = 500
                break
        else:
            response_data = {"error": "Unknown model"}

        return response_data

    return mock_response


def test_successful_analysis_eth(scorer_api_key, mocker):
    """
    Tests that analysis can be requested successfully.
    """
    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/v2/models/score/{address}",
        "queryStringParameters": {"model": "ethereum_activity"},
        "isBase64Encoded": False,
    }
    with mocker.patch("passport.api.fetch", side_effect=mock_post_response):
        # pylint: disable=no-value-for-parameter
        response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 200

    body = json.loads(response["body"])

    assert body["address"] == address
    assert body["details"]["models"]["ethereum_activity"]["score"] == 75


def test_bad_auth():
    """
    Tests that error is thrown if auth is bad.
    """
    event = {
        "headers": {"x-api-key": "bad_auth"},
        "path": f"/v2/models/score/{address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }

    # pylint: disable=no-value-for-parameter
    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 401
    assert json.loads(response["body"])["error"] == "Invalid API Key."


def test_bad_address(scorer_api_key):
    """
    Tests that error is thrown if address is bad.
    """
    bad_address = address[:-1] + "d"

    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/v2/models/score/{bad_address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }
    # pylint: disable=no-value-for-parameter
    response = _handler(event, MockContext())  # type: ignore

    assert response is not None
    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "Invalid address."


def test_bad_model(scorer_api_key):
    """
    Tests that error is thrown if unsupported model is requested.
    """
    model = "bad_model"
    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/v2/models/score/{address}",
        "queryStringParameters": {"model": model},
        "isBase64Encoded": False,
    }
    # pylint: disable=no-value-for-parameter
    response = _handler(event, MockContext())  # type: ignore

    assert response is not None
    assert response["statusCode"] == 400
    assert (
        json.loads(response["body"])["error"]
        == f"Invalid model name(s): {model}. Must be one of {', '.join(settings.MODEL_ENDPOINTS.keys())}"
    )


def test_analysis_eth_unquote_model(scorer_api_key, mocker):
    """
    Tests that the model in the aws_lambda function is urlunquoted.
    """
    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/v2/models/score/{address}",
        "queryStringParameters": {"model": "ethereum_activity%2C%20zksync"},
        "isBase64Encoded": False,
    }
    spy = mocker.spy(v2.aws_lambdas.models_score_GET, "handle_get_analysis")
    # pylint: disable=no-value-for-parameter
    _handler(event, MockContext())  # type: ignore

    # Check that the model is unquoted properly
    spy.assert_called_with(address, "ethereum_activity, zksync")
