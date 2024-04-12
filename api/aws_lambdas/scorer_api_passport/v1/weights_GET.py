"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    with_request_exception_handling,
    with_old_db_connection_close,
)
from ceramic_cache.api.v1 import handle_get_scorer_weights


@with_old_db_connection_close
@with_request_exception_handling
def handler(event, context):
    return format_response(handle_get_scorer_weights())
