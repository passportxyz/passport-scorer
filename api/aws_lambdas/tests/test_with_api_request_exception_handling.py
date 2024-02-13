import json

import pytest
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext
from aws_lambdas.submit_passport.tests.test_submit_passport_lambda import (
    make_test_event,
)
from aws_lambdas.utils import with_api_request_exception_handling
from registry.test.test_passport_submission import mock_passport
from aws_lambdas.exceptions import InvalidRequest


pytestmark = pytest.mark.django_db


def func_to_test(*args, **kwargs):
    return {"greet": "hello world"}


def func_to_test_bad_request(*args, **kwargs):
    raise InvalidRequest("bad request")


def func_to_test_unexpected_error(*args, **kwargs):
    raise Exception("unexpected error")


def test_with_api_request_exception_handling_success(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):

            wrapped_func = with_api_request_exception_handling(func_to_test)

            address = passport_holder_addresses[0]["address"].lower()
            test_event = make_test_event(
                scorer_api_key, address, scorer_community_with_binary_scorer.id
            )

            ret = wrapped_func(test_event, MockContext())

            assert ret["statusCode"] == 200
            assert ret["body"] == '{"greet": "hello world"}'


def test_with_api_request_exception_handling_bad_api_key(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):

            wrapped_func = with_api_request_exception_handling(func_to_test)

            address = passport_holder_addresses[0]["address"].lower()
            test_event = make_test_event(
                scorer_api_key + "=BAD", address, scorer_community_with_binary_scorer.id
            )

            ret = wrapped_func(test_event, MockContext())

            assert ret["statusCode"] == 403
            assert ret["body"] == '{"error": "Unauthorized"}'


def test_with_api_request_exception_handling_bad_request(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):

            wrapped_func = with_api_request_exception_handling(func_to_test_bad_request)

            address = passport_holder_addresses[0]["address"].lower()
            test_event = make_test_event(
                scorer_api_key, address, scorer_community_with_binary_scorer.id
            )

            ret = wrapped_func(test_event, MockContext())

            assert ret["statusCode"] == 400
            assert ret["body"] == '{"error": "Bad request"}'


def test_with_api_request_exception_handling_unexpected_error(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):

            wrapped_func = with_api_request_exception_handling(
                func_to_test_unexpected_error
            )

            address = passport_holder_addresses[0]["address"].lower()
            test_event = make_test_event(
                scorer_api_key, address, scorer_community_with_binary_scorer.id
            )

            ret = wrapped_func(test_event, MockContext())

            assert ret["statusCode"] == 500
            assert ret["body"] == '{"error": "An error has occurred"}'


def test_with_api_request_exception_handling_bad_event(
    mocker,
):

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):

            wrapped_func = with_api_request_exception_handling(
                func_to_test_unexpected_error
            )

            test_event = {"bad": "event"}

            ret = wrapped_func(test_event, MockContext())

            assert ret["statusCode"] == 500
            assert ret["body"] == '{"error": "An error has occurred"}'
