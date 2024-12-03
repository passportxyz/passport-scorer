"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from decimal import Decimal

from asgiref.sync import async_to_sync
from django.db import close_old_connections

from aws_lambdas.utils import (
    with_api_request_exception_handling,
)
from registry.api.v1 import (
    SubmitPassportPayload,
    ahandle_submit_passport,
)
from v2.schema import V2ScoreResponse

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


@with_api_request_exception_handling
def _handler(event, _context, request, user_account, body):
    """
    Handles the incoming events and translates them into Django's context.
    """
    split_url = event["path"].split("/")
    address = split_url[-1]
    scorer_id = split_url[-3]

    v1_score = async_to_sync(ahandle_submit_passport)(
        SubmitPassportPayload(
            address=address,
            scorer_id=scorer_id,
        ),
        user_account,
    )

    threshold = v1_score.evidence.threshold if v1_score.evidence else "20"

    return V2ScoreResponse(
        address=v1_score.address,
        score=v1_score.score,
        passing_score=(
            Decimal(v1_score.score) >= Decimal(threshold) if v1_score.score else False
        ),
        threshold=threshold,
        last_score_timestamp=v1_score.last_score_timestamp,
        expiration_timestamp=v1_score.expiration_date,
        error=v1_score.error,
        stamp_scores=v1_score.stamp_scores,
    )


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
