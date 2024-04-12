"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.utils import (
    with_api_request_exception_handling,
    with_old_db_connection_close,
)
from passport.api import handle_get_analysis


@with_old_db_connection_close
@with_api_request_exception_handling
def handler(event, _context, _request, _user_account, _body):
    """
    Handles the incoming events and translates them into Django's context.
    """

    address = event["path"].split("/")[-1]

    analysis = handle_get_analysis(address)

    return analysis
