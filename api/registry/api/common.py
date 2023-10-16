from datetime import datetime
from typing import Optional

import api_logging as logging

# --- Deduplication Modules
from account.models import Community
from registry.api.schema import (
    CursorPaginatedHistoricalScoreResponse,
    DetailedScoreResponse,
    ErrorMessageResponse,
)
from registry.api.utils import ApiKey, check_rate_limit, with_read_db
from registry.exceptions import InvalidLimitException, api_get_object_or_404
from registry.models import Event, Score
from registry.utils import (
    decode_cursor,
    get_cursor_query_condition,
    get_cursor_tokens_for_results,
)

log = logging.getLogger(__name__)


def get_score_history(
    request,
    scorer_id: int,
    address: Optional[str] = None,
    created_at: str = "",
    token: str = None,
    limit: int = 1000,
) -> CursorPaginatedHistoricalScoreResponse:
    check_rate_limit(request)

    if limit > 1000:
        raise InvalidLimitException()

    community = api_get_object_or_404(Community, id=scorer_id, account=request.auth)

    endpoint = "get_score_history"

    try:
        base_query = with_read_db(Event).filter(
            community__id=community.id, action=Event.Action.SCORE_UPDATE
        )

        cursor = decode_cursor(token) if token else None

        if cursor and "created_at" in cursor:
            created_at = datetime.fromisoformat(cursor.get("created_at"))
        elif created_at:
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = None

        # Scenario 2 - Snapshot for 1 addresses
        # the user has passed in the address, but no created_at
        # In this case only 1 result will be returned
        if address and not created_at:
            scores = base_query.filter(address=address).order_by("-created_at")

            score_response = []
            for score in scores:
                score_data = DetailedScoreResponse(
                    address=score.address,
                    score=score.data["score"],
                    status=Score.Status.DONE,
                    last_score_timestamp=score.created_at.isoformat(),
                    evidence=score.data["evidence"],
                    # below aren't currently stored in the events table, but can be
                    error=None,
                    stamp_scores=None,
                )

                score_response.append(score_data)

            response = CursorPaginatedHistoricalScoreResponse(
                next=None, prev=None, items=score_response
            )
            return response

        # Scenario 2 - Snapshot for 1 addresses and timestamp
        # the user has passed in the created_at and address
        # In this case only 1 result will be returned
        if address and created_at:
            score = (
                base_query.filter(address=address, created_at__lte=created_at)
                .order_by("-created_at")
                .first()
            )

            if not score:
                return CursorPaginatedHistoricalScoreResponse(
                    next=None, prev=None, items=[]
                )

            score.created_at = score.created_at.isoformat()

            score_data = DetailedScoreResponse(
                address=address,
                score=score.data["score"],
                status=Score.Status.DONE,
                last_score_timestamp=score.created_at,
                evidence=score.data["evidence"],
                # below aren't currently stored in the events table, but can be
                error=None,
                stamp_scores=None,
            )

            response = CursorPaginatedHistoricalScoreResponse(
                next=None, prev=None, items=[score_data]
            )
            return response

        # Scenario 3 - Snapshot for all addresses
        # the user has passed in the created_at, but no address
        elif created_at:
            pagination_sort_fields = ["address"]
            filter_condition, field_ordering = get_cursor_query_condition(
                cursor, pagination_sort_fields
            )

            field_ordering.append("-created_at")
            query = (
                base_query.filter(filter_condition)
                .order_by(*field_ordering)
                .distinct("address")
            )

            scores = list(query[:limit])
            for score in scores:
                score.created_at = score.created_at.isoformat()

            if cursor and cursor["d"] == "prev":
                scores.reverse()

            domain = request.build_absolute_uri("/")[:-1]

            page_links = get_cursor_tokens_for_results(
                query,
                domain,
                scores,
                pagination_sort_fields,
                limit,
                [scorer_id],
                endpoint,
            )

            score_response = []
            for score in scores:
                score_data = DetailedScoreResponse(
                    address=score.address,
                    score=score.data["score"],
                    status=Score.Status.DONE,
                    last_score_timestamp=score.created_at,
                    evidence=score.data["evidence"],
                    # below aren't currently stored in the events table, but can be
                    error=None,
                    stamp_scores=None,
                )

                score_response.append(score_data)

            response = CursorPaginatedHistoricalScoreResponse(
                next=page_links["next"], prev=page_links["prev"], items=score_response
            )

            return response
        # # Scenario 4 - Just return history ...
        else:
            pagination_sort_fields = ["id"]
            filter_condition, field_ordering = get_cursor_query_condition(
                cursor, pagination_sort_fields
            )

            field_ordering.insert(0, "address")
            query = (
                base_query.filter(filter_condition)
                .order_by(*field_ordering)
                .distinct("address")
            )

            scores = list(query[:limit])
            for score in scores:
                score.created_at = score.created_at.isoformat()

            if cursor and cursor["d"] == "prev":
                scores.reverse()

            domain = request.build_absolute_uri("/")[:-1]

            page_links = get_cursor_tokens_for_results(
                query,
                domain,
                scores,
                pagination_sort_fields,
                limit,
                [scorer_id],
                endpoint,
            )

            score_response = []
            for score in scores:
                score_data = DetailedScoreResponse(
                    address=score.address,
                    score=score.data["score"],
                    status=Score.Status.DONE,
                    last_score_timestamp=score.created_at,
                    evidence=score.data["evidence"],
                    # below aren't currently stored in the events table, but can be
                    error=None,
                    stamp_scores=None,
                )

                score_response.append(score_data)

            response = CursorPaginatedHistoricalScoreResponse(
                next=page_links["next"], prev=page_links["prev"], items=score_response
            )
            return response

    except Exception as e:
        log.error(
            "Error getting passport scores. scorer_id=%s",
            scorer_id,
            exc_info=True,
        )
        raise e


history_endpoint = {
    "url": "/score/{int:scorer_id}/history",
    "auth": ApiKey(),
    "response": {
        200: CursorPaginatedHistoricalScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    "summary": "Get score history based on timestamp and optional address that is associated with a scorer",
    "description": """
Use this endpoint to get historical Passport score history based on
timestamp and optional user address\n
This endpoint will return a `CursorPaginatedScoreResponse`.\n
The response will include a list of historical scores based on scorer ID and timestamp.\n
If a specific address is provided, then the list will be of max length 1.\n
\n
Note: results will be sorted descending by `["created_at", "id"]`
    """,
    "handler": get_score_history,
}
