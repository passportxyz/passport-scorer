"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import logging

from asgiref.sync import async_to_sync
from django.db import close_old_connections

from aws_lambdas.exceptions import InvalidRequest
from aws_lambdas.utils import (
    with_api_request_exception_handling,
)
from registry.api.v1 import (
    SubmitPassportPayload,
    ahandle_submit_passport,
)

logger = logging.getLogger(__name__)


@with_api_request_exception_handling
def _handler(event, _context, request, user_account, body):
    """
    Handles the incoming events and translates them into Django's context.
    """

    score = async_to_sync(ahandle_submit_passport)(
        SubmitPassportPayload(**body), user_account
    )

    return score


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)


@with_api_request_exception_handling
def _handler_get_score(event, _context, request, user_account, body):
    path = event.get("path", "").split("/")

    if len(path) != 6:
        raise InvalidRequest(f"Invalid path: '{path}'")

    scorer_id = path[3]
    address = path[5]

    logger.info(f"path: '%s', scorer_id: '%s', address: %s", path, scorer_id, address)

    # unquote(event.get("queryStringParameters", {}).get("model_list", ""))

    score = async_to_sync(ahandle_submit_passport)(
        SubmitPassportPayload(
            {
                "scorer_id": scorer_id,
                "address": address,
            }
        ),
        user_account,
    )

    return score


def handler_get_score(*args, **kwargs):
    """
    This handles the new GET request for the score, that also implies doing the same score
    calculation as on the previous POST `submit-passport` request
    """

    close_old_connections()
    return _handler_get_score(*args, **kwargs)
