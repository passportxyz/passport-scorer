"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import logging
import os

from django.http import HttpRequest
from django_ratelimit.exceptions import Ratelimited

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
os.environ.setdefault("CERAMIC_CACHE_SCORER_ID", "1")

import django
from django.conf import settings

logger = logging.getLogger(__name__)

# settings.configure(DEBUG=True)
django.setup()


from registry.api.base import ApiKey, check_rate_limit
from registry.api.v1 import SubmitPassportPayload, handle_submit_passport
from registry.exceptions import Unauthorized

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


def lambda_to_django_request(event):
    """
    Convert a Lambda event into a Django HttpRequest object.
    """
    request = HttpRequest()

    # Basic attributes
    request.method = event["httpMethod"]
    request.path_info = event["path"]
    request.content_type = event["headers"].get("content-type", "")
    request.content_params = {}  # If required, can be populated

    api_key = event["headers"].get("x-api-key", "")

    request.META["HTTP_AUTHORIZATION"] = f"Token {api_key}"

    # Other relevant attributes
    request.META["SERVER_NAME"] = event["headers"].get("host", "")
    request.META["SERVER_PORT"] = event["headers"].get("x-forwarded-port", "")
    request.META["REQUEST_URI"] = event["path"]
    request.META[
        "QUERY_STRING"
    ] = ""  # If needed, adapt from event['queryStringParameters']
    request.META["SERVER_PROTOCOL"] = "HTTP/1.1"

    return request


def handler(event, _context):
    """
    Handles the incoming events and translates them into Django's context.
    """
    try:
        # Authenticate
        api_key_instance = ApiKey()
        request = lambda_to_django_request(event)
        user_account = api_key_instance.authenticate(request, None)

        # rate limit
        check_rate_limit(request)

        if user_account:
            ret = handle_submit_passport(
                SubmitPassportPayload(**event["body"]), user_account
            )
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
