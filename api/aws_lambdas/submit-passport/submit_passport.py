import io
import json
import logging
import os
import sys
from pprint import pprint

from django.http import HttpRequest
from django_ratelimit.decorators import is_ratelimited

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
os.environ.setdefault("CERAMIC_CACHE_SCORER_ID", "1")

import django
from django.conf import settings
from registry.api.base import ApiKey, check_rate_limit

logger = logging.getLogger(__name__)

# settings.configure(DEBUG=True)
django.setup()

if settings.configured:
    print(f"{'-':!>40}")
    print("Django is configured")
    print(f"{'-':!>40}")
else:
    print(f"{'!':!>40}")
    print("Django is NOT configured")
    print(f"{'!':!>40}")


from registry.api.v1 import SubmitPassportPayload, handle_submit_passport

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
    # request.body = event['body'].encode('utf-8')

    # Headers to META
    # for header, value in event["headers"].items():
    #     header_name = "HTTP_" + header.upper().replace("-", "_")
    #     setattr(request, header_name, value)

    request.META["HTTP_AUTHORIZATION"] = event["headers"].get("x-api-key", "")

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
    pprint(event)

    print("CWD: ", os.getcwd())
    print("DIR: ", os.listdir(os.getcwd()))

    try:
        # Authenticate
        api_key_instance = ApiKey()
        request = lambda_to_django_request(event)
        user_account = api_key_instance.authenticate(request, None)

        # rate limit
        check_rate_limit(request)

        if user_account:
            print("Authenticated successfully!")

            payload = json.loads(event["body"])
            print("\nBody:")
            pprint(payload)

            ret = handle_submit_passport(SubmitPassportPayload(**payload), user_account)
            print("\nData to return:", ret)
            return {
                "statusCode": 200,
                "statusDescription": "200 OK",
                "isBase64Encoded": False,
                "headers": {"Content-Type": "application/json"},
                "body": ret.json(),
            }

    except Exception as e:
        logger.exception("Error occured when attempting to submit passport")
        return {
            "statusCode": 400,
            "statusDescription": e,
            "isBase64Encoded": False,
            "headers": {"Content-Type": "text/html"},
            "body": "<h1>An error has occurred</h1>",
        }
