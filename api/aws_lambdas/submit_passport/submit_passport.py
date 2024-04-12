"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from asgiref.sync import async_to_sync
from aws_lambdas.utils import (
    with_api_request_exception_handling,
)
from registry.api.v1 import (
    SubmitPassportPayload,
    ahandle_submit_passport,
)
from django.db import close_old_connections

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


@with_api_request_exception_handling
def _handler(event, _context, request, user_account, body):
    """
    Handles the incoming events and translates them into Django's context.
    """

    score = async_to_sync(ahandle_submit_passport)(
        SubmitPassportPayload(**body), user_account
    )

    return score


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
