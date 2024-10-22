from datetime import datetime, time
from decimal import Decimal
from typing import Any, Dict, List
from urllib.parse import urljoin

import django_filters
from django.conf import settings
from django.core.cache import cache
from ninja import Schema
from ninja_extra.exceptions import APIException

import api_logging as logging
from account.models import Community
from ceramic_cache.models import CeramicCache
from registry.api.schema import (
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
    atrack_apikey_usage,
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
    CreatedAtIsRequiredException,
    CreatedAtMalFormedException,
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
from v2.api import (
    api,
)

METADATA_URL = urljoin(settings.PASSPORT_PUBLIC_URL, "stampMetadata.json")

log = logging.getLogger(__name__)


@api_router.get(
    "/stamps/{scorer_id}/score/{address}",
    auth=aapi_key,
    response={
        200: V2ScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    operation_id="v2_api_api_stamps_a_submit_passport",
    summary="Retrieve Stamp-based unique humanity score for a specified address",
    description="""This is the primary endpoint that integrators should use. This endpoint will return the latest score and Stamp data for a single address.<br /><br /><a href="https://docs.passport.xyz/building-with-passport/passport-api-v2/api-reference" target="_blank">Docs</a>""",
    tags=["Stamp API"],
)
@atrack_apikey_usage(track_response=True)
async def a_submit_passport(
    request, scorer_id: int, address: str
) -> DetailedScoreResponse:
    check_rate_limit(request)
    try:
        if not request.api_key.submit_passports:
            raise InvalidAPIKeyPermissions()

        return await ahandle_submit_passport(
            SubmitPassportPayload(address=address, scorer_id=str(scorer_id)),
            request.auth,
        )

    except APIException as e:
        raise e
    except Exception as e:
        log.exception("Error submitting passport: %s", e)
        raise InternalServerErrorException("Unexpected error while submitting passport")


def extract_score_data(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract score data from either the legacy or new data structure.

    Args:
        event_data: Dictionary containing score event data

    Returns:
        Dictionary with normalized score data
    """
    # Handle legacy format (with 'fields' key)
    if "fields" in event_data:
        return event_data["fields"]
    # Handle new format (direct score data)
    return event_data


class EventFilter(django_filters.FilterSet):
    created_at__lte = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    address = django_filters.CharFilter(field_name="address")
    community__id = django_filters.NumberFilter(field_name="community__id")
    action = django_filters.ChoiceFilter(
        choices=Event.Action.choices, field_name="action"
    )

    class Meta:
        model = Event
        fields = ["created_at", "address", "community__id", "action"]


@api_router.get(
    "/stamps/{scorer_id}/score/{address}/history",
    auth=ApiKey(),
    response={
        200: V2ScoreResponse | NoScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    operation_id="v2_api_api_stamps_get_score_history",
    summary="Retrieve historical Stamp-based unique humanity score for a specified address",
    description="""This endpoint will return the historical score and Stamp data for a single address at a specified time. **Note:** To access this endpoint, you must submit your use case and be approved by the Passport team. To do so, please fill out the following form, making sure to provide a detailed description of your use case. The Passport team typically reviews and responds to form responses within 48 hours.<br /><br />[Request access](https://forms.gle/4GyicBfhtHW29eEu8)<br /><br /><a href="https://docs.passport.xyz/building-with-passport/passport-api-v2/api-reference" target="_blank">Docs</a>""",
    tags=["Stamp API"],
)
@track_apikey_usage(track_response=False)
def get_score_history(
    request,
    scorer_id: int,
    address: str,
    created_at: str,
):
    if not request.api_key.historical_endpoint:
        raise InvalidAPIKeyPermissions()
    if not created_at:
        raise CreatedAtIsRequiredException()

    check_rate_limit(request)
    community = api_get_object_or_404(Community, id=scorer_id, account=request.auth)

    try:
        filterset = EventFilter(
            data={
                "community__id": community.id,
                "action": Event.Action.SCORE_UPDATE,
                "address": address,
                "created_at__lte": created_at,
            },
            queryset=with_read_db(Event),
        )

        score_event = filterset.qs.order_by("-created_at").first()

        if not score_event:
            return NoScoreResponse(
                address=address, status=f"No Score Found for {address} at {created_at}"
            )

        # Extract and normalize score data from either format
        score_data = extract_score_data(score_event.data)

        # Get evidence data, defaulting to empty dict if not present
        evidence = score_data.get("evidence") or {}
        threshold = evidence.get("threshold", "0")

        # Handle score extraction for both formats
        if "evidence" in score_data and "rawScore" in evidence:
            score = score_data["evidence"]["rawScore"]
        else:
            score = score_data.get("score", "0")

        return V2ScoreResponse(
            address=address,
            score=score,
            passing_score=(Decimal(score) >= Decimal(threshold) if score else False),
            threshold=threshold,
            last_score_timestamp=score_data.get("last_score_timestamp"),
            expiration_timestamp=score_data.get("expiration_date"),
            error=score_data.get("error"),
            stamp_scores=score_data.get("stamp_scores"),
        )

    except Exception as e:
        log.error(
            "Error getting passport scores. scorer_id=%s",
            scorer_id,
            exc_info=True,
        )
        raise e


@api_router.get(
    "/stamps/metadata",
    summary="Receive all Stamps available in Passport",
    description="""<a href="https://docs.passport.xyz/building-with-passport/passport-api-v2/api-reference" target="_blank">Docs</a>""",
    auth=ApiKey(),
    response={
        200: List[StampDisplayResponse],
        500: ErrorMessageResponse,
    },
    operation_id="v2_api_api_stamps_stamp_display",
    tags=["Stamp API"],
)
@track_apikey_usage(track_response=False)
def stamp_display(request) -> List[StampDisplayResponse]:
    check_rate_limit(request)
    return fetch_all_stamp_metadata()


@api_router.get(
    "/stamps/{str:address}",
    auth=ApiKey(),
    response={
        200: CursorPaginatedStampCredentialResponse,
        400: ErrorMessageResponse,
        401: ErrorMessageResponse,
    },
    operation_id="v2_api_api_stamps_get_passport_stamps",
    summary="Retrieve the Stamps that a specified account has verified.",
    description="""Use this endpoint to retrieve the Stamps verified by a specified address.<br /><br />This endpoint will return a `CursorPaginatedStampCredentialResponse`.<br /><br /><a href="https://docs.passport.xyz/building-with-passport/passport-api-v2/api-reference" target="_blank">Docs</a>""",
    exclude_unset=True,
    tags=["Stamp API"],
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
