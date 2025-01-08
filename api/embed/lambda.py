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
from typing import Any, Dict, List, Tuple

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
from ninja import Schema

from account.models import Account, AccountAPIKey, AccountAPIKeyAnalytics
from ceramic_cache.api.schema import CacheStampPayload
from ceramic_cache.api.v1 import handle_add_stamps
from registry.api.utils import (
    is_valid_address,
)
from registry.exceptions import (
    InvalidAddressException,
)

from .api import AccountAPIKeySchema, AddStampsPayload

# pylint: enable=wrong-import-position

logger = logging.getLogger(__name__)


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


# Define the pattern
pattern = r"/([^/]+)/?$"


def get_address(value: str) -> str:
    match = re.search(pattern, value)
    if match:
        product_id = match.group(1)
        print(f"Extracted product_id: {product_id}")
        return product_id
    else:
        raise ValueError("Invalid path. Expecting values like: '/some/path/<address>/'")


@with_embed_request_exception_handling
def _handler_save_stamps(event, _context, body, _sensitive_date):
    """
    Request handler implementation.

    Note:
    If required perform authentication, but the expectation is that
    this handler will be called via a private load balancer in our VPC
    """

    add_stamps_payload = AddStampsPayload(**body)
    _address = get_address(event["path"])
    address_lower = _address.lower()
    if not is_valid_address(address_lower):
        raise InvalidAddressException()

    add_stamps_response = handle_add_stamps(
        address_lower,
        [
            CacheStampPayload(
                address=address_lower,
                provider=s.get("credentialSubject", {}).get("provider"),
                stamp=s,
            )
            for s in add_stamps_payload.stamps
        ],
        add_stamps_payload.scorer_id,
    )

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
    except AccountAPIKey.DoesNotExist:
        raise Unauthorized()

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": AccountAPIKeySchema.from_orm(api_key).model_dump_json(),
    }


def lambda_handler_get_rate_limit(*args, **kwargs):
    close_old_connections()
    return _handler_get_rate_limit(*args, **kwargs)
