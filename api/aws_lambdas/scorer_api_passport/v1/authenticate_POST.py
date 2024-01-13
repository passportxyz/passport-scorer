"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    parse_body,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import CacaoVerifySubmit, handle_authenticate


@with_request_exception_handling
def handler(event, context):
    body = parse_body(event)

    payload = CacaoVerifySubmit(**body)

    return format_response(handle_authenticate(payload))
