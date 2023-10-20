"""
This module provides utils to manage Passport API requests in AWS Lambda.
"""

import base64
import os
from functools import wraps
from typing import Any, Dict, Tuple

from structlog.contextvars import bind_contextvars

from aws_lambdas.exceptions import InvalidRequest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
os.environ.setdefault("CERAMIC_CACHE_SCORER_ID", "1")

import json

import django


django.setup()

import api_logging as logging

logger = logging.getLogger(__name__)

from registry.exceptions import Unauthorized
from ceramic_cache.api.v1 import JWTDidAuthentication

auth = JWTDidAuthentication()


def authenticate_and_get_address(event) -> str:
    token = get_token_from_event(event)
    valid_token = auth.get_validated_token(token)
    did = valid_token["did"]
    return did.split(":")[-1]


def get_token_from_event(event) -> str:
    logger.info("headers %s" % json.dumps(event.get("headers", {})))

    return event.get("headers", {}).get("authorization", "").split(" ")[-1]


def parse_body(event):
    if event["isBase64Encoded"]:
        body = json.loads(base64.b64decode(event["body"]).decode("utf-8"))
    elif "body" in event and event["body"]:
        body = json.loads(event["body"])
    else:
        body = {}

    return body


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
            }

            status, message = error_descriptions.get(
                type(e), (500, "An error has occurred")
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
