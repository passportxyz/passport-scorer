"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    preprocess_event,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import handle_get_stamps


@with_request_exception_handling
def handler(event, context):
    address, _ = preprocess_event(event, context)

    return format_response(handle_get_stamps(address))
