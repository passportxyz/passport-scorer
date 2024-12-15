"""
This module provides a handler to manage embed API requests in AWS Lambda.
"""

import os

# This will make sure that non-essential django apps will not be loaded
os.environ["LAMBDA_ONLY_APPS"] = "True"

import json
import logging
import re
from typing import Any, Dict, List, Tuple

from ninja import Schema
from structlog.contextvars import bind_contextvars  # noqa: E402

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
)

""" Load the django apps after the aws_lambdas.utils """
from django.db import close_old_connections

from ceramic_cache.api.schema import CacheStampPayload
from ceramic_cache.api.v1 import handle_add_stamps
from ceramic_cache.models import CeramicCache
from registry.api.utils import (
    is_valid_address,
)
from registry.exceptions import (
    InvalidAddressException,
)

logger = logging.getLogger(__name__)


def with_embed_request_exception_handling(func):
    """
    This wrapper is meant to be used for **embed** API handler, which will be called form the iam

    """
    # TODO: adjust according to needs

    def wrapper(event, context, *args):
        try:
            bind_contextvars(request_id=context.aws_request_id)
            logger.info("Received event: %s", event)

            # Parse the body and call the function
            body = parse_body(event)

            return func(event, context, body)
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
                "body": json.dumps({"error": message}),
            }

            logger.exception(
                "Error occurred with Passport API. Response: %s", json.dumps(response)
            )
            return response

    return wrapper


class AddStampsPayload(Schema):
    scorer_id: int
    stamps: List[Any]


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
def _handler(event, _context, body):
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


def lambda_handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
