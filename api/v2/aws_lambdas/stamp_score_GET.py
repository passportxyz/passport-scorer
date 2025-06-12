"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import close_old_connections

from aws_lambdas.utils import (
    with_api_request_exception_handling,
)

from ..api.api_stamps import handle_scoring_for_account

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


@with_api_request_exception_handling
def _handler(event, _context, request, user_account, body):
    """
    Handles the incoming events and translates them into Django's context.
    """
    split_url = event["path"].split("/")
    address = split_url[-1]
    scorer_id = split_url[-3]

    if scorer_id < 0:
        scorer_id = settings.DEMO_API_SCORER_ID

    return async_to_sync(handle_scoring_for_account)(address, scorer_id, user_account)


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
