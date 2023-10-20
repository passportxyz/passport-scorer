"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    authenticate_and_get_address,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import get_detailed_score_response_for_address


@with_request_exception_handling
def handler(event, context):
    address = authenticate_and_get_address(event)

    return format_response(get_detailed_score_response_for_address(address))
