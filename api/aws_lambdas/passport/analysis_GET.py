"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import asyncio

from django.db import close_old_connections
from passport.api import handle_get_analysis

from aws_lambdas.utils import (
    with_api_request_exception_handling,
)


@with_api_request_exception_handling
def _handler(event, _context, _request, _user_account, _body):
    """
    Handles the incoming events and translates them into Django's context.
    """

    address = event["path"].split("/")[-1]
    model_list = event.get("queryStringParameters", {}).get("model_list", "")

    loop = asyncio.get_event_loop()
    response = loop.run_until_complete(handle_get_analysis(address, model_list))

    return response


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
