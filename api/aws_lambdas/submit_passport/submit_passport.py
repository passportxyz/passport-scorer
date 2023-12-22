"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import base64
import json

from asgiref.sync import async_to_sync
from django.http import HttpRequest

from aws_lambdas.utils import format_response, with_request_exception_handling
from registry.api.utils import ApiKey, check_rate_limit
from registry.api.v1 import (DetailedScoreResponse, SubmitPassportPayload,
                             ahandle_submit_passport)

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


def lambda_to_django_request(api_key):
    """
    Convert a Lambda event into a Django HttpRequest object.
    """
    request = HttpRequest()
    request.META["X-Api-Key"] = api_key

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
    request = lambda_to_django_request(api_key)
    user_account = api_key_instance.authenticate(request, api_key)

    # rate limit
    check_rate_limit(request)

    if event["isBase64Encoded"]:
        body = json.loads(base64.b64decode(event["body"]).decode("utf-8"))
    else:
        body = json.loads(event["body"])

    if user_account:
        score = async_to_sync(ahandle_submit_passport)(
            SubmitPassportPayload(**body), user_account
        )
        # TODO: preferably we would have a 1:1 mapping of the fields for DetailedScoreResponse
        # or if not, then specify a resolver for stamp_scores
        ret = DetailedScoreResponse.from_orm(score)
        ret.stamp_scores = score.stamp_scores

        return format_response(ret)
