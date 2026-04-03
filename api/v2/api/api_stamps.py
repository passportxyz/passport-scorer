from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import django_filters
from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import now as django_now
from ninja_extra.exceptions import APIException

import api_logging as logging
from account.models import (
    Account,
    Community,
    Nonce,
    WalletGroupCommunityClaim,
    WalletGroupMembership,
)
from ceramic_cache.models import CeramicCache
from registry.api.schema import (
    CursorPaginatedStampCredentialResponse,
    ErrorMessageResponse,
    NoScoreResponse,
    StampDisplayResponse,
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
    aget_scorer_by_id,
    fetch_all_stamp_metadata,
)
from registry.atasks import ascore_passport
from registry.exceptions import (
    CreatedAtIsRequiredException,
    InternalServerErrorException,
    InvalidAddressException,
    InvalidAPIKeyPermissions,
    InvalidLimitException,
    api_get_object_or_404,
)
from registry.human_points_utils import get_possible_points_data, get_user_points_data
from registry.models import Event, Passport, Score
from registry.utils import (
    decode_cursor,
    encode_cursor,
    get_utc_time,
    reverse_lazy_with_query,
)
from scorer_weighted.models import Scorer
from v2.schema import LinkedScoreResponse, PointsData, V2ScoreResponse

from ..exceptions import ScoreDoesNotExist
from .router import api_router

METADATA_URL = urljoin(settings.PASSPORT_PUBLIC_URL, "stampMetadata.json")

log = logging.getLogger(__name__)


async def handle_scoring_for_account(address: str, scorer_id: str, user_account):
    # Get community object
    user_community = await aget_scorer_by_id(scorer_id, user_account)
    return await ahandle_scoring(address, user_community)


async def ahandle_scoring(address: str, community):
    address_lower = address.lower()
    if not is_valid_address(address_lower):
        raise InvalidAddressException()

    # Check if address is in a wallet group
    group_info = await _get_wallet_group(address_lower)

    if not group_info:
        # No group - existing single-wallet flow
        return await _score_single_address(address_lower, community)

    group_id, group_addresses = group_info

    # Determine canonical wallet for this community
    canonical = await _get_or_set_canonical(
        group_id, address_lower, community
    )

    # Score all wallets in the group individually, then merge
    combined_response = await _score_wallet_group(
        canonical, group_addresses, community
    )

    if address_lower == canonical:
        return combined_response
    else:
        return _build_non_canonical_response(address_lower, combined_response)


async def _get_wallet_group(
    address: str,
) -> Optional[Tuple[int, list[str]]]:
    """Look up wallet group for an address. Returns (group_id, [addresses]) or None."""
    try:
        membership = await WalletGroupMembership.objects.aget(address=address)
    except WalletGroupMembership.DoesNotExist:
        return None

    group_addresses = [
        m async for m in WalletGroupMembership.objects.filter(
            group_id=membership.group_id
        ).values_list("address", flat=True)
    ]
    return (membership.group_id, group_addresses)


async def _get_or_set_canonical(
    group_id: int, requesting_address: str, community: Community
) -> str:
    """Get or create canonical wallet claim for a group+community.

    If an existing claim's score has expired, release it and let the
    requesting address claim it.
    """
    try:
        claim = await WalletGroupCommunityClaim.objects.aget(
            group_id=group_id, community=community
        )
        # Check if canonical wallet's score is still valid
        try:
            canonical_score = await Score.objects.select_related("passport").aget(
                passport__address=claim.canonical_address,
                passport__community=community,
            )
            if (
                canonical_score.expiration_date
                and canonical_score.expiration_date < get_utc_time()
            ):
                # Expired - release claim, let requesting address take over
                await claim.adelete()
                raise WalletGroupCommunityClaim.DoesNotExist()
        except Score.DoesNotExist:
            # No score yet for canonical address - keep the claim
            pass

        return claim.canonical_address
    except WalletGroupCommunityClaim.DoesNotExist:
        # No claim exists - requesting address becomes canonical
        # Use get_or_create to handle races (unique_together protects us)
        claim, _ = await WalletGroupCommunityClaim.objects.aget_or_create(
            group_id=group_id,
            community=community,
            defaults={"canonical_address": requesting_address},
        )
        return claim.canonical_address


async def _score_single_address(address: str, community: Community) -> V2ScoreResponse:
    """Score a single address (no wallet group). Preserves original flow."""
    scorer = await community.aget_scorer()
    scorer_type = scorer.type

    db_passport, _ = await Passport.objects.aupdate_or_create(
        address=address,
        community=community,
    )

    score, _ = await Score.objects.select_related("passport").aget_or_create(
        passport=db_passport,
        defaults=dict(score=None, status=Score.Status.PROCESSING),
    )

    await ascore_passport(community, db_passport, address, score)
    await score.asave()

    return format_v2_score_response(score, scorer_type)


async def _score_wallet_group(
    canonical_address: str,
    group_addresses: list[str],
    community: Community,
) -> V2ScoreResponse:
    """Score all wallets in a group individually, then merge by provider for the canonical wallet."""
    scorer = await community.aget_scorer()
    scorer_type = scorer.type

    # Score each wallet through the existing pipeline
    wallet_scores: dict[str, Score] = {}
    for addr in group_addresses:
        db_passport, _ = await Passport.objects.aupdate_or_create(
            address=addr, community=community
        )
        score, _ = await Score.objects.select_related("passport").aget_or_create(
            passport=db_passport,
            defaults=dict(score=None, status=Score.Status.PROCESSING),
        )
        await ascore_passport(community, db_passport, addr, score)
        await score.asave()
        wallet_scores[addr] = score

    # Merge stamps by provider: take first valid (non-deduped) stamp per provider
    # Process canonical wallet first so its stamps take priority
    ordered_addresses = [canonical_address] + [
        a for a in group_addresses if a != canonical_address
    ]

    merged_stamps: Dict[str, Any] = {}
    for addr in ordered_addresses:
        score = wallet_scores[addr]
        if not score.stamps:
            continue
        for provider, stamp_data in score.stamps.items():
            if provider not in merged_stamps and not stamp_data.get("dedup"):
                merged_stamps[provider] = stamp_data

    # Calculate combined raw_score from merged stamps using scorer weights
    weights = scorer.weights or {}
    try:
        from account.models import Customization

        customization = await Customization.objects.aget(scorer_id=community.pk)
        weights.update(await customization.aget_customization_dynamic_weights())
    except Exception:
        pass

    combined_raw_score = Decimal(0)
    merged_stamp_scores = {}
    earliest_expiration = None
    for provider, stamp_data in merged_stamps.items():
        weight = Decimal(weights.get(provider, 0))
        combined_raw_score += weight
        merged_stamp_scores[provider] = str(weight)

        exp_date = stamp_data.get("expiration_date")
        if exp_date and (earliest_expiration is None or exp_date < earliest_expiration):
            earliest_expiration = exp_date

    threshold = Decimal(
        scorer.threshold if hasattr(scorer, "threshold") else "20"
    )
    is_passing = combined_raw_score >= threshold

    # Update canonical wallet's Score with merged results
    canonical_score = wallet_scores[canonical_address]
    canonical_score.score = Decimal(1) if is_passing else Decimal(0)
    canonical_score.evidence = {
        "type": "ThresholdScoreCheck",
        "success": is_passing,
        "rawScore": str(combined_raw_score),
        "threshold": str(threshold),
    }
    canonical_score.stamps = merged_stamps
    canonical_score.stamp_scores = merged_stamp_scores
    canonical_score.status = Score.Status.DONE
    canonical_score.last_score_timestamp = get_utc_time()
    if earliest_expiration:
        from datetime import datetime, timezone

        if isinstance(earliest_expiration, str):
            canonical_score.expiration_date = datetime.fromisoformat(
                earliest_expiration
            )
        else:
            canonical_score.expiration_date = earliest_expiration
    await canonical_score.asave()

    return format_v2_score_response(canonical_score, scorer_type)


def _build_non_canonical_response(
    address: str, canonical_response: V2ScoreResponse
) -> V2ScoreResponse:
    """Build a zero-score response for non-canonical wallets with linked_score."""
    return V2ScoreResponse(
        address=address,
        score=Decimal(0),
        passing_score=False,
        threshold=canonical_response.threshold,
        last_score_timestamp=canonical_response.last_score_timestamp,
        expiration_timestamp=canonical_response.expiration_timestamp,
        error=None,
        stamps={},
        linked_score=LinkedScoreResponse(
            address=canonical_response.address,
            score=canonical_response.score,
            passing_score=canonical_response.passing_score,
            last_score_timestamp=canonical_response.last_score_timestamp,
            expiration_timestamp=canonical_response.expiration_timestamp,
            threshold=canonical_response.threshold,
            stamps=canonical_response.stamps,
        ),
    )


def format_v2_score_response(
    score: Score,
    scorer_type: Scorer.Type,
    points_data: Dict[str, Any] = None,
    possible_points_data: Dict[str, Any] = None,
) -> V2ScoreResponse:
    raw_score = score.evidence.get("rawScore", "0") if score.evidence else "0"
    threshold = score.evidence.get("threshold", "20") if score.evidence else "20"

    raw_score = Decimal(0) if raw_score is None else Decimal(raw_score)
    threshold = Decimal(0) if threshold is None else Decimal(threshold)

    # Convert points_data dict to PointsData schema if provided
    formatted_points_data = None
    formatted_possible_points_data = None
    if points_data:
        formatted_points_data = PointsData(
            total_points=points_data["total_points"],
            is_eligible=points_data["is_eligible"],
            multiplier=points_data["multiplier"],
            breakdown=points_data["breakdown"],
        )
    if possible_points_data:
        formatted_possible_points_data = PointsData(
            total_points=possible_points_data["total_points"],
            is_eligible=possible_points_data["is_eligible"],
            multiplier=possible_points_data["multiplier"],
            breakdown=possible_points_data["breakdown"],
        )

    return V2ScoreResponse(
        address=score.passport.address,
        score=raw_score,
        passing_score=(raw_score >= threshold),
        threshold=threshold,
        last_score_timestamp=(
            score.last_score_timestamp.isoformat()
            if score.last_score_timestamp
            else None
        ),
        expiration_timestamp=(
            score.expiration_date.isoformat() if score.expiration_date else None
        ),
        error=score.error,
        stamps=score.stamps if score.stamps is not None else {},
        points_data=formatted_points_data,
        possible_points_data=formatted_possible_points_data,
    )


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
async def a_submit_passport(request, scorer_id: int, address: str) -> V2ScoreResponse:
    check_rate_limit(request)

    try:
        if int(scorer_id) < 0:
            scorer_id = settings.DEMO_API_SCORER_ID
    except ValueError:
        pass

    try:
        return await handle_scoring_for_account(address, str(scorer_id), request.auth)
    except APIException as e:
        raise e
    except Exception as e:
        log.exception("Error submitting passport: %s", e)
        raise InternalServerErrorException(
            "Unexpected error while submitting passport"
        ) from e


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
        200: V2ScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse | NoScoreResponse,
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

    try:
        if int(scorer_id) < 0:
            scorer_id = settings.DEMO_API_SCORER_ID
    except ValueError:
        pass

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
            raise ScoreDoesNotExist(
                address, f"No Score Found for {address} at {created_at}"
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
            stamps=score_data.get("stamps"),
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
        f"""{domain}{
            reverse_lazy_with_query(
                "registry:get_passport_stamps",
                args=[address],
                query_kwargs={
                    "token": encode_cursor(d="next", id=next_id),
                    "limit": limit,
                },
            )
        }"""
        if has_more_stamps
        else None
    )

    prev_url = (
        f"""{domain}{
            reverse_lazy_with_query(
                "registry:get_passport_stamps",
                args=[address],
                query_kwargs={
                    "token": encode_cursor(d="prev", id=prev_id),
                    "limit": limit,
                },
            )
        }"""
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
