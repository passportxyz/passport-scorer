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

    print(f"EVENT: \n***************\n{event}\n***************\n")
    address = event["path"].split("/")[-1]

    loop = asyncio.get_event_loop()
    # DynamoDB resource defined above is attached to this loop:
    #   if you use asyncio.run instead
    #   you will encounter "Event loop closed" exception
    analysis = loop.run_until_complete(handle_get_analysis(address))

    return analysis


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
