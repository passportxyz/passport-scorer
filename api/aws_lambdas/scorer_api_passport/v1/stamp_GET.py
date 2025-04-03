"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from django.db import close_old_connections

from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    with_request_exception_handling,
)
from aws_lambdas.utils import get_address_param
from ceramic_cache.api.v1 import handle_get_stamps


@with_request_exception_handling
def _handler(event, context):
    address = get_address_param(event)

    return format_response(handle_get_stamps(address))


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
