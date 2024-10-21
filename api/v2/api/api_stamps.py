from datetime import datetime
from decimal import Decimal
from typing import List
from urllib.parse import urljoin

from django.conf import settings
from django.core.cache import cache
from ninja_extra.exceptions import APIException

import api_logging as logging
from account.models import Community
from ceramic_cache.models import CeramicCache
from registry.api.schema import (
    CursorPaginatedHistoricalScoreResponse,
    CursorPaginatedStampCredentialResponse,
    DetailedScoreResponse,
    ErrorMessageResponse,
    NoScoreResponse,
    StampDisplayResponse,
    SubmitPassportPayload,
)
from registry.api.utils import (
    ApiKey,
    aapi_key,
    check_rate_limit,
    is_valid_address,
    track_apikey_usage,
    with_read_db,
)
from registry.api.v1 import (
    ahandle_submit_passport,
    fetch_all_stamp_metadata,
)
from registry.exceptions import (
    CreatedAtIsRequired,
    InternalServerErrorException,
    InvalidAddressException,
    InvalidAPIKeyPermissions,
    InvalidLimitException,
    api_get_object_or_404,
)
from registry.models import Event, Score
from registry.utils import (
    decode_cursor,
    encode_cursor,
    reverse_lazy_with_query,
)

from .api import (
    api,
)
from .schema import V2ScoreResponse

METADATA_URL = urljoin(settings.PASSPORT_PUBLIC_URL, "stampMetadata.json")

log = logging.getLogger(__name__)


@api.get(
    "/stamps/{int:scorer_id}/score/{str:address}",
    auth=aapi_key,
    response={
        200: V2ScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Retrieve a Passport score for an address",
    description=f"""Use this endpoint to fetch the score for a specific address and scorer\n
A new score will be calculated based on the user's current Stamps.
""",
    tags=["Stamp Analysis"],
)
@atrack_apikey_usage(track_response=True)
async def a_submit_passport(request, scorer_id: int, address: str) -> V2ScoreResponse:
    check_rate_limit(request)
    try:
        if not request.api_key.submit_passports:
            raise InvalidAPIKeyPermissions()

        v1_score = await ahandle_submit_passport(
            SubmitPassportPayload(address=address, scorer_id=scorer_id), request.auth
        )
        threshold = v1_score.evidence.threshold if v1_score.evidence else "20"
        score = v1_score.evidence.rawScore if v1_score.evidence else v1_score.score

        return V2ScoreResponse(
            address=v1_score.address,
            score=score,
            passing_score=(
                Decimal(v1_score.score) >= Decimal(threshold)
                if v1_score.score
                else False
            ),
            threshold=threshold,
            last_score_timestamp=v1_score.last_score_timestamp,
            expiration_timestamp=v1_score.expiration_date,
            error=v1_score.error,
            stamp_scores=v1_score.stamp_scores,
        )
    except APIException as e:
        raise e
    except Exception as e:
        log.exception("Error submitting passport: %s", e)
        raise InternalServerErrorException("Unexpected error while submitting passport")


@api.get(
    "/stamps/{int:scorer_id}/score/{str:address}/history",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse | NoScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Get score history based on timestamp and optional address that is associated with a scorer",
    description="""
Use this endpoint to get a historical Passport score based on
timestamp.\n
This endpoint will return a `DetailedScoreResponse` if a score exists at the passed in timestamp.\n
\n
\n
To access this endpoint, you must submit your use case and be approved by the Passport team. To do so, please fill out the following form, making sure to provide a detailed description of your use case. The Passport team typically reviews and responds to form responses within 48 hours. <a href="https://forms.gle/4GyicBfhtHW29eEu8" target="_blank">https://forms.gle/4GyicBfhtHW29eEu8</a>
    """,
    include_in_schema=False,
    tags=["Stamp Analysis"],
)
@track_apikey_usage(track_response=False)
def get_score_history(
    request,
    scorer_id: int,
    address: str,
    created_at: str = "",
):
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


@api.get(
    "/stamps/metadata",
    summary="Receive all Stamps available in Passport",
    description="""**WARNING**: This endpoint is in beta and is subject to change.""",
    auth=ApiKey(),
    response={
        200: List[StampDisplayResponse],
        500: ErrorMessageResponse,
    },
    tags=["Stamp Analysis"],
)
@track_apikey_usage(track_response=False)
def stamp_display(request) -> List[StampDisplayResponse]:
    check_rate_limit(request)
    return fetch_all_stamp_metadata()


@api.get(
    "/stamps/{str:address}",
    auth=ApiKey(),
    response={
        200: CursorPaginatedStampCredentialResponse,
        400: ErrorMessageResponse,
        401: ErrorMessageResponse,
    },
    summary="Receive Stamps verified by submitted Passports",
    description="""Use this endpoint to fetch the passport for a specific address\n
This endpoint will return a `CursorPaginatedStampCredentialResponse`.\n
**WARNING**: The **include_metadata** feature is in beta, the metadata response format may change in the future.\n
""",
    # This prevents returning {metadata: None} in the response
    exclude_unset=True,
    tags=["Stamp Analysis"],
)
@track_apikey_usage(track_response=False)
def get_passport_stamps(
    request,
    address: str,
    token: str = "",
    limit: int = 1000,
    include_metadata: bool = False,
) -> CursorPaginatedStampCredentialResponse:
    check_rate_limit(request)

    if limit > 1000:
        raise InvalidLimitException()

    # ref: https://medium.com/swlh/how-to-implement-cursor-pagination-like-a-pro-513140b65f32

    address = address.lower()

    if not is_valid_address(address):
        raise InvalidAddressException()

    query = CeramicCache.objects.order_by("-id").filter(
        address=address, deleted_at__isnull=True
    )

    cursor = decode_cursor(token) if token else {}
    direction = cursor.get("d")
    id_ = cursor.get("id")

    if direction == "next":
        # note we use lt here because we're querying in descending order
        cacheStamps = list(query.filter(id__lt=id_)[:limit])

    elif direction == "prev":
        cacheStamps = list(query.filter(id__gt=id_).order_by("id")[:limit])
        cacheStamps.reverse()

    else:
        cacheStamps = list(query[:limit])

    has_more_stamps = has_prev_stamps = False
    next_id = prev_id = 0

    if cacheStamps:
        next_id = cacheStamps[-1].pk
        prev_id = cacheStamps[0].pk

        has_more_stamps = query.filter(id__lt=next_id).exists()
        has_prev_stamps = query.filter(id__gt=prev_id).exists()

    stamps = [
        {
            "version": "1.0.0",
            "credential": cache.stamp,
            **(
                {"metadata": fetch_stamp_metadata_for_provider(cache.provider)}
                if include_metadata
                else {}
            ),
        }
        for cache in cacheStamps
    ]

    domain = request.build_absolute_uri("/")[:-1]

    next_url = (
        f"""{domain}{reverse_lazy_with_query(
            "registry:get_passport_stamps",
            args=[address],
            query_kwargs={"token": encode_cursor(d="next", id=next_id), "limit": limit},
        )}"""
        if has_more_stamps
        else None
    )

    prev_url = (
        f"""{domain}{reverse_lazy_with_query(
            "registry:get_passport_stamps",
            args=[address],
            query_kwargs={"token": encode_cursor(d="prev", id=prev_id), "limit": limit},
        )}"""
        if has_prev_stamps
        else None
    )

    response = CursorPaginatedStampCredentialResponse(
        next=next_url, prev=prev_url, items=stamps
    )

    return response


def fetch_stamp_metadata_for_provider(provider: str):
    metadataByProvider = cache.get("metadataByProvider")

    try:
        if metadataByProvider is None:
            metadata = fetch_all_stamp_metadata()
            metadataByProvider = {
                stamp.name: {
                    "name": stamp.name,
                    "description": stamp.description,
                    "hash": stamp.hash,
                    "group": group.name,
                    "platform": {
                        "name": platform.name,
                        "id": platform.id,
                        "icon": platform.icon,
                        "description": platform.description,
                        "connectMessage": platform.connectMessage,
                    },
                }
                for platform in metadata
                for group in platform.groups
                for stamp in group.stamps
            }
            cache.set("metadataByProvider", metadataByProvider, 60 * 60)
    except Exception:
        log.exception("Error fetching external metadata")
        raise InternalServerErrorException(
            "Error fetching external stamp metadata for provider " + provider
        )

    return metadataByProvider.get(provider)
