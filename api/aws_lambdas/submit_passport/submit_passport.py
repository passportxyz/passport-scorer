"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import base64
import logging
import os

from django.http import HttpRequest
from django_ratelimit.exceptions import Ratelimited

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
os.environ.setdefault("CERAMIC_CACHE_SCORER_ID", "1")

import json

import django
from django.conf import settings

logger = logging.getLogger(__name__)

# settings.configure(DEBUG=True)
django.setup()


from asgiref.sync import async_to_sync
from registry.api.utils import ApiKey, check_rate_limit
from registry.api.v1 import (
    DetailedScoreResponse,
    SubmitPassportPayload,
    ahandle_submit_passport,
)
from registry.exceptions import Unauthorized

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


def lambda_to_django_request(api_key):
    """
    Convert a Lambda event into a Django HttpRequest object.
    """
    request = HttpRequest()
    request.META["X-Api-Key"] = api_key

    return request


def handler(event, _context):
    """
    Handles the incoming events and translates them into Django's context.
    """
    try:
        logger.info("Received event: %s", event)
        api_key = event["headers"].get("x-api-key", "")
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
            ret.stamp_scores = score.points

            return {
                "statusCode": 200,
                "statusDescription": "200 OK",
                "isBase64Encoded": False,
                "headers": {"Content-Type": "application/json"},
                "body": ret.json(),
            }

    except (Unauthorized, Ratelimited) as e:
        status, message = {
            Unauthorized: (403, "<h1>Unauthorized</h1>"),
            Ratelimited: (
                429,
                "<h1>You have been rate limited. Please try again later.</h1>",
            ),
        }.get(type(e), (400, "<h1>An error has occurred</h1>"))
        logger.exception("Error occurred when attempting to submit passport: %s", e)
        return {
            "statusCode": status,
            "statusDescription": str(e),
            "isBase64Encoded": False,
            "headers": {"Content-Type": "text/html"},
            "body": message,
        }
