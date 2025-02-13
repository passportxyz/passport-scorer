"""
This module provides a handler to manage embed API requests in AWS Lambda.
"""

import os

# This will make sure that non-essential django apps will not be loaded
os.environ["LAMBDA_ONLY_APPS"] = "True"

# pylint: disable=wrong-import-position
import json
import logging
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

from account.models import Nonce
from ceramic_cache.api.v1 import CacaoVerifySubmit, handle_authenticate

# pylint: enable=wrong-import-position

logger = logging.getLogger(__name__)


def with_app_api_no_auth_request_exception_handling(func):
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


@with_app_api_no_auth_request_exception_handling
def _lambda_handler_account_nonce(_event, _context, body, sensitive_date):
    http_method = _event["httpMethod"]
    body = None
    headers = None

    if http_method == "GET":
        nonce = Nonce.create_nonce(ttl=300)
        body = json.dumps({"nonce": nonce.nonce})
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Cross-Origin-Opener-Policy": "same-origin",
        }
    else:
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Cross-Origin-Opener-Policy": "same-origin",
        }
        body = ""

    return {
        "statusCode": 200,
        "headers": headers,
        "body": body,
    }


def lambda_handler_account_nonce(*args, **kwargs):
    close_old_connections()
    return _lambda_handler_account_nonce(*args, **kwargs)


@with_app_api_no_auth_request_exception_handling
def _lambda_handler_authenticate(_event, _context, body, sensitive_date):
    http_method = _event["httpMethod"]
    body = None
    headers = None

    if http_method == "POST":
        cacao_verify_submit = CacaoVerifySubmit(**body)
        access_token_response = handle_authenticate(cacao_verify_submit)
        body = access_token_response.model_dump_json()
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Access-Control-Allow-Headers": "*",
        }
    else:
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Access-Control-Allow-Headers": "*",
        }
        body = ""

    return {
        "statusCode": 200,
        "headers": headers,
        "body": body,
    }


def lambda_handler_authenticate(*args, **kwargs):
    close_old_connections()
    return _lambda_handler_authenticate(*args, **kwargs)
