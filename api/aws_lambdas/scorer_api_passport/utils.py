"""
This module provides utils to manage Passport API requests in AWS Lambda.
"""

import base64
import logging
import os
from functools import wraps
from typing import Any, Dict, Tuple

from structlog.contextvars import bind_contextvars

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
os.environ.setdefault("CERAMIC_CACHE_SCORER_ID", "1")

import json

import django

logger = logging.getLogger(__name__)

django.setup()

from registry.exceptions import Unauthorized


def authenticate_did_and_get_address(token: str) -> str:
    # TODO
    return token


def get_token_from_event(event) -> str:
    return event.get("headers", {}).get("Authorization", "").split(" ")[-1]


def preprocess_event(event, context):
    bind_contextvars(request_id=context.aws_request_id)

    logger.info("Received event: %s", event)

    token = get_token_from_event(event)
    address = authenticate_did_and_get_address(token)

    if event["isBase64Encoded"]:
        body = json.loads(base64.b64decode(event["body"]).decode("utf-8"))
    elif "body" in event and event["body"]:
        body = json.loads(event["body"])
    else:
        body = {}

    return address, body


def with_request_exception_handling(func):
    @wraps(func)
    def wrapper(event, context):
        try:
            return func(event, context)
        except Exception as e:
            error_descriptions: Dict[Any, Tuple[int, str]] = {
                Unauthorized: (403, "<h1>Unauthorized</h1>"),
            }

            status, message = error_descriptions.get(
                type(e), (400, "<h1>An error has occurred</h1>")
            )

            logger.exception(f"Error occurred with Passport API: {e}")

            return {
                "statusCode": status,
                "statusDescription": str(e),
                "isBase64Encoded": False,
                "headers": {"Content-Type": "text/html"},
                "body": message,
            }

    return wrapper


def format_response(ret: Any):
    return {
        "statusCode": 200,
        "statusDescription": "200 OK",
        "isBase64Encoded": False,
        "headers": {"Content-Type": "application/json"},
        "body": ret.json() if hasattr(ret, "json") else json.dumps(ret),
    }
