"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    format_response,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import handle_get_scorer_weights
from django.db import close_old_connections


@with_request_exception_handling
def _handler(event, context):
    return format_response(handle_get_scorer_weights())


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
