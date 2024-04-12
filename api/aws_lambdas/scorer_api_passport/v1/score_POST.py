"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    authenticate_and_get_address,
    format_response,
    with_request_exception_handling,
    parse_body,
)
from ceramic_cache.api.v1 import get_detailed_score_response_for_address
from django.db import close_old_connections


@with_request_exception_handling
def _handler(event, context):
    address = authenticate_and_get_address(event)
    body = parse_body(event)
    alternate_scorer_id = body.get("alternate_scorer_id", None)

    return format_response(
        get_detailed_score_response_for_address(address, alternate_scorer_id)
    )


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
