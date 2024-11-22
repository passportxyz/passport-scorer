"""
This module provides a handler to manage embed API requests in AWS Lambda.
"""

import os

# This will make sure that non-essential django apps will not be loaded
os.environ["LAMBDA_ONLY_APPS"] = "True"

import json
import logging
from typing import Any, Dict, Tuple

from django.db import close_old_connections
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
    Ratelimited,
    Unauthorized,
    parse_body,
)
from ceramic_cache.models import CeramicCache

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


@with_embed_request_exception_handling
def _handler(event, _context, body):
    """
    Request handler implementation.

    Note:
    If required perform authentication, but the expectation is that
    this handler will be called via a private load balancer in our VPC
    """

    print("body:", body)

    # TODO: enable read from DB
    # TODO: example of interacting with redis
    stamps = list(CeramicCache.objects.all()[:3])

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"stamp_count": len(stamps)}),
    }


def lambda_handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
