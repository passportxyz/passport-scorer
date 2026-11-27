"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import close_old_connections

from aws_lambdas.utils import (
    with_api_request_exception_handling,
)
from registry.exceptions import InvalidAddressException

from ..api.api_stamps import handle_chain_wallet_score, handle_scoring_for_account

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


@with_api_request_exception_handling
def _handler(event, _context, request, user_account, body):
    """
    Handles the incoming events and translates them into Django's context.
    """
    split_url = event["path"].split("/")
    address = split_url[-1]
    if len(split_url) == 8 and split_url[4:6] == ["score", "eip155"]:
        try:
            chain_id = int(split_url[6])
            scorer_id = int(split_url[3])
        except ValueError as exc:
            raise InvalidAddressException("Invalid EIP-155 wallet identity") from exc
        return async_to_sync(handle_chain_wallet_score)(
            address, chain_id, scorer_id, user_account, request.api_key
        )

    scorer_id = split_url[-3]

    try:
        if int(scorer_id) < 0:
            scorer_id = settings.DEMO_API_SCORER_ID
    except ValueError:
        pass

    return async_to_sync(handle_scoring_for_account)(
        address,
        scorer_id,
        user_account,
        include_linked_wallets=request.api_key.linked_wallet_breakdown,
    )


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
