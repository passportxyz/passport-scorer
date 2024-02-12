"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import base64
import json

from asgiref.sync import async_to_sync
from aws_lambdas.utils import format_response, with_api_request_exception_handling
from django.http import HttpRequest
from registry.api.v1 import (
    DetailedScoreResponse,
    SubmitPassportPayload,
    ahandle_submit_passport,
)
from registry.api.utils import save_api_key_analytics

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


@with_api_request_exception_handling
def handler(event, _context, request, user_account, body):
    """
    Handles the incoming events and translates them into Django's context.
    """

    score = async_to_sync(ahandle_submit_passport)(
        SubmitPassportPayload(**body), user_account
    )

    return format_response(score)
