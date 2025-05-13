"""
This module provides a handler to manage embed API requests in AWS Lambda.
"""

import os

# This will make sure that non-essential django apps will not be loaded
os.environ["LAMBDA_ONLY_APPS"] = "True"

# pylint: disable=wrong-import-position
import json
import logging
import re
from typing import Any, Dict, Tuple

from structlog.contextvars import bind_contextvars

from aws_lambdas.exceptions import InvalidRequest
from aws_lambdas.utils import (
    RESPONSE_HEADERS,
    APIException,
    DataError,
    IntegrityError,
    InterfaceError,
    InternalError,
    InvalidToken,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
    Unauthorized,
    parse_body,
    strip_event,
)

""" Load the django apps after the aws_lambdas.utils """  # pylint: disable=pointless-string-statement
from django.db import close_old_connections

from account.models import AccountAPIKey, Community
from registry.api.utils import (
    validate_address_and_convert_to_lowercase,
)

from .api import (
    AccountAPIKeySchema,
    AddStampsPayload,
    handle_embed_add_stamps,
    handle_get_score,
)

# pylint: enable=wrong-import-position

logger = logging.getLogger(__name__)

pattern_internal_embed_score = re.compile(
    "^/internal/embed/score/(?P<scorer_id>[^/]+)/(?P<address>[^/]+)[/]?$"
)
pattern_internal_save_stamps = re.compile(
    "^/internal/embed/stamps/(?P<address>[^/]+)[/]?$"
)


def get_path_params(event: any, regex) -> dict:
    path = event.get("path", "")
    match = regex.match(path)
    if match:
        return match.groupdict()
    else:
        raise InvalidRequest(f"Invalid path. Expecting values like: '{regex.pattern}'")


def with_embed_request_exception_handling(func):
    """
    This wrapper is meant to be used for **embed** API handler, which will be called form the iam

    """

    def wrapper(_event, context, *args):
        try:
            bind_contextvars(request_id=context.aws_request_id)
            sensitive_data, event = strip_event(_event)

            logger.info("Received event: %s", event)

            # Parse the body and call the function
            body = parse_body(event)

            return func(event, context, body, sensitive_data)
        except Exception as e:
            if isinstance(e, APIException):
                status = e.status_code
                message = str(e.detail)

            else:
                # TODO: do we want rate limiting here?
                # ratelimit_msg = (
                #     get_analysis_api_rate_limited_msg()
                #     if event.get("path", "").startswith("/passport/")
                #     else get_passport_api_rate_limited_msg()
                # )

                error_descriptions: Dict[Any, Tuple[int, str]] = {
                    Unauthorized: (403, "Unauthorized"),
                    InvalidToken: (403, "Invalid token"),
                    InvalidRequest: (400, "Bad request"),
                    # Ratelimited: (429, ratelimit_msg),
                    InterfaceError: (500, "DB Error: InterfaceError"),
                    DataError: (500, "DB Error: DataError"),
                    OperationalError: (500, "DB Error: OperationalError"),
                    IntegrityError: (500, "DB Error: IntegrityError"),
                    InternalError: (500, "DB Error: InternalError"),
                    ProgrammingError: (500, "DB Error: ProgrammingError"),
                    NotSupportedError: (500, "DB Error: NotSupportedError"),
                }

                status, message = error_descriptions.get(
                    type(e), (400, "An error has occurred")
                )

                # If a custom message was passed into the exception, use that
                message = e.args[0] if e.args else message

            bind_contextvars(
                statusCode=status,
                statusCategory="4XX" if (status >= 400 and status < 500) else "5XX",
            )
            response = {
                "statusCode": status,
                "statusCategory": "4XX" if (status >= 400 and status < 500) else "5XX",
                "statusDescription": str(e),
                "isBase64Encoded": False,
                "headers": RESPONSE_HEADERS,
                "body": json.dumps({"detail": message}),
            }

            logger.exception(
                "Error occurred with Passport API. Response: %s", json.dumps(response)
            )
            return response

    return wrapper


@with_embed_request_exception_handling
def _handler_save_stamps(event, _context, body, _sensitive_date):
    """
    Request handler implementation.

    Note:
    If required perform authentication, but the expectation is that
    this handler will be called via a private load balancer in our VPC
    """

    add_stamps_payload = AddStampsPayload(**body)
    _address = get_path_params(event, pattern_internal_save_stamps)["address"]
    address_lower = validate_address_and_convert_to_lowercase(_address)

    add_stamps_response = handle_embed_add_stamps(address_lower, add_stamps_payload)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": add_stamps_response.model_dump_json(),
    }


def lambda_handler_save_stamps(*args, **kwargs):
    close_old_connections()
    return _handler_save_stamps(*args, **kwargs)


@with_embed_request_exception_handling
def _handler_get_rate_limit(_event, _context, body, sensitive_date):
    try:
        api_key = AccountAPIKey.objects.get_from_key(sensitive_date["x-api-key"])
    except AccountAPIKey.DoesNotExist as exc:
        raise Unauthorized() from exc

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": AccountAPIKeySchema.from_orm(api_key).model_dump_json(),
    }


def lambda_handler_get_rate_limit(*args, **kwargs):
    close_old_connections()
    return _handler_get_rate_limit(*args, **kwargs)


@with_embed_request_exception_handling
def _handler_get_score(event, _context, body, sensitive_date):
    try:
        try:
            params = get_path_params(event, pattern_internal_embed_score)
            score = handle_get_score(params["scorer_id"], params["address"])
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": score.model_dump_json(),
            }
        except Community.DoesNotExist as exc:
            raise InvalidRequest("Invalid scorer_id") from exc

    except AccountAPIKey.DoesNotExist as exc:
        raise Unauthorized() from exc


def lambda_handler_get_score(*args, **kwargs):
    close_old_connections()
    return _handler_get_score(*args, **kwargs)
