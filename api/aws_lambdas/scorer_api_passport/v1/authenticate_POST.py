"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from django.db import close_old_connections

from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    parse_body,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import CacaoVerifySubmit, handle_authenticate


@with_request_exception_handling
def _handler(event, context):
    body = parse_body(event)

    payload = CacaoVerifySubmit(**body)

    return format_response(handle_authenticate(payload))


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
