"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    authenticate_and_get_address,
    format_response,
    parse_body,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import get_detailed_score_response_for_address

DUMMY_MARKER = "import django.db stuff after this line"
# django.db needs to be imported after the aws helpers
from django.conf import settings
from django.db import close_old_connections


@with_request_exception_handling
def _handler(event, context):
    address = authenticate_and_get_address(event)
    body = parse_body(event)
    alternate_scorer_id = (
        body.get("alternate_scorer_id", None) or settings.CERAMIC_CACHE_SCORER_ID
    )

    return format_response(
        get_detailed_score_response_for_address(address, alternate_scorer_id)
    )


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
