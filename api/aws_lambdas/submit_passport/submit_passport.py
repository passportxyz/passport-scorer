"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import base64
import json

from asgiref.sync import async_to_sync
from aws_lambdas.utils import format_response, with_request_exception_handling
from django.http import HttpRequest
from registry.api.utils import ApiKey, check_rate_limit, save_api_key_analytics
from registry.api.v1 import (
    DetailedScoreResponse,
    SubmitPassportPayload,
    ahandle_submit_passport,
)

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


def lambda_to_django_request(api_key, event):
    """
    Convert a Lambda event into a Django HttpRequest object.
    """
    request = HttpRequest()
    request.META["X-Api-Key"] = api_key
    request.path = event["path"]

    return request


def strip_event(event) -> tuple:
    """
    Strips the event of all sensitive fields.
    This will return a tuple like: (sensitive_data_dict, event_without_sensitive_data)
    """
    sensitive_data = {}
    headers = event.get("headers", {})
    if "x-api-key" in headers:
        sensitive_data["x-api-key"] = headers["x-api-key"]
        headers["x-api-key"] = "***"
    return sensitive_data, event


@with_request_exception_handling
def handler(_event, _context):
    """
    Handles the incoming events and translates them into Django's context.
    """
    sensitive_data, event = strip_event(_event)
    api_key = sensitive_data.get("x-api-key", "")
    # Authenticate
    api_key_instance = ApiKey()
    request = lambda_to_django_request(api_key, event)
    user_account = api_key_instance.authenticate(request, api_key)

    if event["isBase64Encoded"]:
        body = json.loads(base64.b64decode(event["body"]).decode("utf-8"))
    else:
        body = json.loads(event["body"])

    # rate limit
    check_rate_limit(request)

    try:
        if user_account:
            score = async_to_sync(ahandle_submit_passport)(
                SubmitPassportPayload(**body), user_account
            )

            save_api_key_analytics(
                api_key_id=request.api_key.id,
                path=event["path"],
                path_segments=event["path"].split("/"),
                query_params=event["path"].split("/"),
                headers=event["headers"],
                payload=body,
                response=score.dict(),
                response_skipped=False,
                error="",
            )

            return format_response(score)

    except Exception as e:
        save_api_key_analytics(
            api_key_id=request.api_key.id,
            path=event["path"],
            path_segments=event["path"].split("/"),
            query_params=event["path"].split("/"),
            headers=event["headers"],
            payload=body,
            response={},
            response_skipped=False,
            error=str(e),
        )
