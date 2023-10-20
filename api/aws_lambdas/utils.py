"""
This module provides utils to manage Passport API requests in AWS Lambda.
"""

import os
from functools import wraps
from typing import Any, Dict, Tuple

from structlog.contextvars import bind_contextvars

from aws_lambdas.exceptions import InvalidRequest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
os.environ.setdefault("CERAMIC_CACHE_SCORER_ID", "1")

import json

import django
from django_ratelimit.exceptions import Ratelimited

django.setup()

import api_logging as logging

logger = logging.getLogger(__name__)

from registry.exceptions import Unauthorized

RESPONSE_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "*",
    "Access-Control-Allow-Headers": "Accept,Accept-Encoding,Authorization,Content-Type,Dnt,Origin,User-Agent,X-Csrftoken,X-Requested-With,X-Api-Key",
}


def with_request_exception_handling(func):
    @wraps(func)
    def wrapper(event, context):
        try:
            bind_contextvars(request_id=context.aws_request_id)

            logger.info("Received event: %s", event)

            return func(event, context)
        except Exception as e:
            error_descriptions: Dict[Any, Tuple[int, str]] = {
                Unauthorized: (403, "Unauthorized"),
                InvalidRequest: (400, "Bad request"),
                Ratelimited: (
                    429,
                    "You have been rate limited. Please try again later.",
                ),
            }

            status, message = error_descriptions.get(
                type(e), (400, "An error has occurred")
            )

            logger.exception(f"Error occurred with Passport API: {e}")

            return {
                "statusCode": status,
                "statusDescription": str(e),
                "isBase64Encoded": False,
                "headers": RESPONSE_HEADERS,
                "body": '{"error": "' + message + '"}',
            }

    return wrapper


def format_response(ret: Any):
    return {
        "statusCode": 200,
        "statusDescription": "200 OK",
        "isBase64Encoded": False,
        "headers": RESPONSE_HEADERS,
        "body": ret.json() if hasattr(ret, "json") else json.dumps(ret),
    }
