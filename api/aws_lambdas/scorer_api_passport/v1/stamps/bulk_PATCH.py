"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    authenticate_and_get_address,
    parse_body,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import CacheStampPayload, handle_patch_stamps


@with_request_exception_handling
def handler(event, context):
    address = authenticate_and_get_address(event)
    body = parse_body(event)

    payload = [CacheStampPayload(**p) for p in body]

    return format_response(handle_patch_stamps(address, payload))
