"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    authenticate_and_get_address,
    format_response,
    parse_body,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import DeleteStampPayload, handle_delete_stamps
from django.db import close_old_connections


@with_request_exception_handling
def _handler(event, context):
    address = authenticate_and_get_address(event)
    body = parse_body(event)

    payload = [DeleteStampPayload(**p) for p in body]

    return format_response(handle_delete_stamps(address, payload))


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
