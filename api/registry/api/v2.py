from datetime import datetime
from typing import List, Optional

import api_logging as logging

# --- Deduplication Modules
from account.models import Community
from django.db.models import Q
from ninja import Router
from registry.api import v1
from registry.api.v1 import with_read_db
from registry.models import Score
from registry.utils import (
    decode_cursor,
    encode_cursor,
    get_cursor_query_condition,
    reverse_lazy_with_query,
)

from ..exceptions import InvalidLimitException, api_get_object_or_404
from .base import ApiKey, check_rate_limit
from .schema import (
    CursorPaginatedScoreResponse,
    CursorPaginatedStampCredentialResponse,
    DetailedScoreResponse,
    ErrorMessageResponse,
    SigningMessageResponse,
    StampDisplayResponse,
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
    auth=v1.aapi_key,
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
async def a_submit_passport(
    request, payload: SubmitPassportPayload
) -> DetailedScoreResponse:
    return await v1.a_submit_passport(request, payload)


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
        base_query = (
            with_read_db(Score)
            .filter(passport__community__id=user_community.id)
            .select_related("passport")
        )

        filter_condition = Q()
        field_ordering = None
        cursor = decode_cursor(token) if token else None
        if cursor:
            cursor = decode_cursor(token)
            cursor["last_score_timestamp"] = datetime.fromisoformat(
                cursor.get("last_score_timestamp")
            )
            filter_condition, field_ordering = get_cursor_query_condition(cursor)

        else:
            field_ordering = ["last_score_timestamp", "id"]

            if address:
                filter_condition &= Q(passport__address=address)

            if last_score_timestamp__gt:
                filter_condition &= Q(last_score_timestamp__gt=last_score_timestamp__gt)

            if last_score_timestamp__gte:
                filter_condition &= Q(
                    last_score_timestamp__gte=last_score_timestamp__gte
                )

        has_more_scores = has_prev_scores = False
        next_cursor = prev_cursor = {}

        query = base_query.filter(filter_condition).order_by(*field_ordering)
        scores = query[:limit]
        scores = list(scores)

        if cursor and cursor["d"] == "prev":
            scores.reverse()

        if scores:
            next_id = scores[-1].id
            next_lts = scores[-1].last_score_timestamp
            prev_id = scores[0].id
            prev_lts = scores[0].last_score_timestamp

            next_cursor = dict(
                d="next",
                id=next_id,
                last_score_timestamp=next_lts.isoformat(),
                address=address,
                last_score_timestamp__gt=last_score_timestamp__gt,
                last_score_timestamp__gte=last_score_timestamp__gte,
            )
            prev_cursor = dict(
                d="prev",
                id=prev_id,
                last_score_timestamp=prev_lts.isoformat(),
                address=address,
                last_score_timestamp__gt=last_score_timestamp__gt,
                last_score_timestamp__gte=last_score_timestamp__gte,
            )

            next_filter_cond, _ = get_cursor_query_condition(next_cursor)
            prev_filter_cond, _ = get_cursor_query_condition(prev_cursor)

            has_more_scores = base_query.filter(next_filter_cond).exists()
            has_prev_scores = base_query.filter(prev_filter_cond).exists()

        domain = request.build_absolute_uri("/")[:-1]

        next_url = (
            f"""{domain}{reverse_lazy_with_query(
                "registry_v2:get_scores",
                args=[scorer_id],
                query_kwargs={"token": encode_cursor(**next_cursor), "limit": limit},
            )}"""
            if has_more_scores
            else None
        )

        prev_url = (
            f"""{domain}{reverse_lazy_with_query(
                "registry_v2:get_scores",
                args=[scorer_id],
                query_kwargs={"token": encode_cursor(**prev_cursor), "limit": limit},
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
    # This prevents returning {metadata: None} in the response
    exclude_unset=True,
)
def get_passport_stamps(
    request,
    address: str,
    token: str = "",
    limit: int = 1000,
    include_metadata: bool = False,
) -> CursorPaginatedStampCredentialResponse:
    return v1.get_passport_stamps(request, address, token, limit, include_metadata)


@router.get(
    "/stamp-metadata",
    description="""**WARNING**: This endpoint is in beta and is subject to change.""",
    auth=ApiKey(),
    response={
        200: List[StampDisplayResponse],
        500: ErrorMessageResponse,
    },
)
def stamp_display(request) -> List[StampDisplayResponse]:
    return v1.stamp_display(request)


@router.get(
    "/gtc-stake/{address}",
    description="Get self and community staking amounts based on address and round id",
    auth=ApiKey(),
    response=v1.GqlResponse,
)
def get_gtc_stake(request, address: str):
    return v1.get_gtc_stake(request, address)
