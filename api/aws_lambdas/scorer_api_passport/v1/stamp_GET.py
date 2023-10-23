"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.exceptions import InvalidRequest
from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import handle_get_stamps


def get_address_param(event):
    if (
        "queryStringParameters" not in event
        or "address" not in event["queryStringParameters"]
    ):
        raise InvalidRequest("Missing address parameter")
    return event["queryStringParameters"]["address"]


@with_request_exception_handling
def handler(event, context):
    address = get_address_param(event)

    return format_response(handle_get_stamps(address))
