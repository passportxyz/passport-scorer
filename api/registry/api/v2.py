from datetime import datetime
from typing import List, Optional

import api_logging as logging

# --- Deduplication Modules
from account.models import Community
from django.db.models import Q
from ninja import Router
from registry.api import v1
from registry.api.v1 import ScoreFilter, with_read_db
from registry.models import Score
from registry.utils import decode_cursor, encode_cursor, reverse_lazy_with_query

from ..exceptions import InvalidLimitException, api_get_object_or_404
from .base import ApiKey, check_rate_limit
from .schema import (
    CursorPaginatedScoreResponse,
    CursorPaginatedStampCredentialResponse,
    DetailedScoreResponse,
    ErrorMessageResponse,
    SigningMessageResponse,
    SubmitPassportPayload,
)

log = logging.getLogger(__name__)

router = Router()

analytics_router = Router()


@router.get(
    "/signing-message",
    auth=ApiKey(),
    response={
        200: SigningMessageResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
    },
    summary="Submit passport for scoring",
    description="""Use this API to get a message to sign and a nonce to use when submitting your passport for scoring.""",
)
def signing_message(request) -> SigningMessageResponse:
    return v1.signing_message(request)


@router.post(
    "/submit-passport",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Submit passport for scoring",
    description="""Use this API to submit your passport for scoring.\n
This API will return a `DetailedScoreResponse` structure with status **PROCESSING** immediatly while your passport is being pulled from storage and the scoring algorithm is run.\n
You need to check for the status of the operation by calling the `/score/{int:scorer_id}/{str:address}` API. The operation will have finished when the status returned is **DONE**
""",
)
def submit_passport(request, payload: SubmitPassportPayload) -> DetailedScoreResponse:
    return v1.submit_passport(request, payload)


@router.get(
    "/score/{int:scorer_id}/{str:address}",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Get score for an address that is associated with a scorer",
    description="""Use this endpoint to fetch the score for a specific address that is associated with a scorer\n
This endpoint will return a `DetailedScoreResponse`. This endpoint will also return the status of the asynchronous operation that was initiated with a request to the `/submit-passport` API.\n
""",
)
def get_score(request, address: str, scorer_id: int) -> DetailedScoreResponse:
    return v1.get_score(request, address, scorer_id)


@router.get(
    "/score/{int:scorer_id}",
    auth=ApiKey(),
    response={
        200: CursorPaginatedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Get scores for all addresses that are associated with a scorer",
    description="""Use this endpoint to fetch the scores for all addresses that are associated with a scorer\n
This endpoint will return a `CursorPaginatedScoreResponse`.\n
\n

Note: results will be sorted ascending by `["last_score_timestamp", "id"]`
""",
)
def get_scores(
    request,
    scorer_id: int,
    address: Optional[str] = None,
    last_score_timestamp__gt: str = "",
    last_score_timestamp__gte: str = "",
    token: str = None,
    limit: int = 1000,
) -> CursorPaginatedScoreResponse:
    check_rate_limit(request)

    if limit > 1000:
        raise InvalidLimitException()

    # Get community object
    user_community = api_get_object_or_404(
        Community, id=scorer_id, account=request.auth
    )
    try:
        ordering_fields_asc = ["last_score_timestamp", "id"]
        ordering_fields_desc = ["-last_score_timestamp", "-id"]
        base_query = (
            with_read_db(Score)
            .filter(passport__community__id=user_community.id)
            .select_related("passport")
        )

        cursor = decode_cursor(token)
        direction = cursor.get("d")
        score_id = cursor.get("id")
        last_score_timestamp = cursor.get("lts")
        last_score_timestamp = (
            datetime.fromisoformat(last_score_timestamp)
            if last_score_timestamp
            else None
        )

        if direction == "next":
            query = base_query.filter(
                Q(last_score_timestamp__gt=last_score_timestamp)
                | (
                    Q(last_score_timestamp__gte=last_score_timestamp)
                    & Q(id__gt=score_id)
                )
            ).order_by(*ordering_fields_asc)
        elif direction == "prev":
            query = base_query.filter(
                Q(last_score_timestamp__lt=last_score_timestamp)
                | (
                    Q(last_score_timestamp__lte=last_score_timestamp)
                    & Q(id__gt=score_id)
                )
            ).order_by(*ordering_fields_desc)
        else:
            query = base_query.order_by(*ordering_fields_asc)

        query = query[:limit]
        has_more_scores = has_prev_scores = False

        # Technically we could just pass request.GET to the filter. But since we have the parameters defined
        # anyways (because we need them for the generated docs) we might as well use them explicitly in the
        # filter_values.
        scores = ScoreFilter(
            {
                "address": address,
                "last_score_timestamp__gt": last_score_timestamp__gt,
                "last_score_timestamp__gte": last_score_timestamp__gte,
            },
            queryset=query,
        ).qs

        scores = list(query)

        if direction == "prev":
            scores.reverse()

        if scores:
            next_id = scores[-1].id
            next_lts = scores[-1].last_score_timestamp
            prev_id = scores[0].id
            prev_lts = scores[0].last_score_timestamp

            has_more_scores = base_query.filter(id__gt=next_id).exists()
            has_prev_scores = base_query.filter(id__lt=prev_id).exists()

        domain = request.build_absolute_uri("/")[:-1]

        next_url = (
            f"""{domain}{reverse_lazy_with_query(
                "registry_v2:get_scores",
                args=[scorer_id],
                query_kwargs={"token": encode_cursor(d="next", id=next_id, lts=next_lts.isoformat()), "limit": limit},
            )}"""
            if has_more_scores
            else None
        )

        prev_url = (
            f"""{domain}{reverse_lazy_with_query(
                "registry_v2:get_scores",
                args=[scorer_id],
                query_kwargs={"token": encode_cursor(d="prev", id=prev_id, lts=prev_lts.isoformat()), "limit": limit},
            )}"""
            if has_prev_scores
            else None
        )

        response = CursorPaginatedScoreResponse(
            next=next_url, prev=prev_url, items=scores
        )

        return response

    except Exception as e:
        log.error(
            "Error getting passport scores. scorer_id=%s",
            scorer_id,
            exc_info=True,
        )
        raise e


@router.get(
    "/stamps/{str:address}",
    auth=ApiKey(),
    response={
        200: CursorPaginatedStampCredentialResponse,
        400: ErrorMessageResponse,
        401: ErrorMessageResponse,
    },
    summary="Get passport for an address",
    description="""Use this endpoint to fetch the passport for a specific address\n
This endpoint will return a `CursorPaginatedStampCredentialResponse`.\n
""",
)
def get_passport_stamps(
    request, address: str, token: str = None, limit: int = 1000
) -> CursorPaginatedStampCredentialResponse:
    return v1.get_passport_stamps(request, address, token, limit)


@router.get(
    "/gtc-stake/{address}",
    description="Get self and community staking amounts based on address and round id",
    auth=ApiKey(),
    response=v1.GqlResponse,
)
def get_gtc_stake(request, address: str):
    return v1.get_gtc_stake(request, address)
