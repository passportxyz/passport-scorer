"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.utils import get_address_param
from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    with_request_exception_handling,
    with_old_db_connection_close,
)
from ceramic_cache.api.v1 import handle_get_stamps


@with_old_db_connection_close
@with_request_exception_handling
def handler(event, context):
    address = get_address_param(event)

    return format_response(handle_get_stamps(address))
