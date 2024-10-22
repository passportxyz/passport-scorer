from datetime import datetime
from typing import Optional

import api_logging as logging

# --- Deduplication Modules
from account.models import Community
from registry.api.schema import (
    CursorPaginatedHistoricalScoreResponse,
    DetailedScoreResponse,
    ErrorMessageResponse,
    NoScoreResponse,
)
from registry.api.utils import ApiKey, check_rate_limit, with_read_db
from registry.exceptions import (
    CreatedAtIsRequired,
    InvalidAPIKeyPermissions,
    InvalidLimitException,
    api_get_object_or_404,
)
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
    address: str,
    created_at: str,
) -> DetailedScoreResponse | NoScoreResponse:
    if not request.api_key.historical_endpoint:
        raise InvalidAPIKeyPermissions()

    if not created_at:
        raise CreatedAtIsRequired()

    check_rate_limit(request)

    community = api_get_object_or_404(Community, id=scorer_id, account=request.auth)

    try:
        base_query = with_read_db(Event).filter(
            community__id=community.id, action=Event.Action.SCORE_UPDATE
        )

        score = (
            base_query.filter(
                address=address, created_at__lte=datetime.fromisoformat(created_at)
            )
            .order_by("-created_at")
            .first()
        )

        if not score:
            return NoScoreResponse(
                address=address, status=f"No Score Found for {address} at {created_at}"
            )

        return DetailedScoreResponse(
            address=address,
            score=score.data["score"],
            status=Score.Status.DONE,
            last_score_timestamp=score.created_at.isoformat(),
            evidence=score.data["evidence"],
            # below aren't currently stored in the events table, but can be
            error=None,
            stamp_scores=None,
        )

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
        200: DetailedScoreResponse | NoScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    "summary": "Get score history based on timestamp and optional address that is associated with a scorer",
    "description": """
Use this endpoint to get a historical Passport score based on
timestamp.\n
This endpoint will return a `DetailedScoreResponse` if a score exists at the passed in timestamp.\n
\n
\n
To access this endpoint, you must submit your use case and be approved by the Passport team. To do so, please fill out the following form, making sure to provide a detailed description of your use case. The Passport team typically reviews and responds to form responses within 48 hours. <a href="https://forms.gle/4GyicBfhtHW29eEu8" target="_blank">https://forms.gle/4GyicBfhtHW29eEu8</a>
    """,
    "handler": get_score_history,
}
