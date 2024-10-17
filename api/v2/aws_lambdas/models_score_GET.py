"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import asyncio
from urllib.parse import unquote

from django.db import close_old_connections

from aws_lambdas.utils import (
    with_api_request_exception_handling,
)

# The following needs to be imported after aws_lambdas.utils
from passport.api import handle_get_analysis  # noqa


@with_api_request_exception_handling
# pylint: disable=unused-argument
def _handler(event, context, request, user_account, body):
    """
    Handles the incoming events and translates them into Django's context.
    """

    address = event["path"].split("/")[-1]
    model_list = unquote(event.get("queryStringParameters", {}).get("model", ""))

    loop = asyncio.get_event_loop()
    response = loop.run_until_complete(handle_get_analysis(address, model_list))

    return response


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
