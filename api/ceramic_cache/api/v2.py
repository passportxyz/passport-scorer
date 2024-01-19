"""Ceramic Cache API"""

from typing import Dict, List

import api_logging as logging
import requests
from django.conf import settings
from ninja import Router
from registry.api.v1 import DetailedScoreResponse
from registry.models import Score

from ..exceptions import (
    InternalServerException,
    InvalidDeleteCacheRequestException,
    TooManyStampsException,
)
from ..models import CeramicCache
from .v1 import (
    AccessTokenResponse,
    CacaoVerifySubmit,
    CachedStampResponse,
    CacheStampPayload,
    DeleteStampPayload,
    GetStampResponse,
    GetStampsWithScoreResponse,
    JWTDidAuth,
)
from .v1 import authenticate as authenticate_v1
from .v1 import get_address_from_did, get_detailed_score_response_for_address
from .v1 import get_score as get_score_v1
from .v1 import get_utc_time, handle_get_scorer_weights

log = logging.getLogger(__name__)

router = Router()


def migrate_stamp_to_v2(v1_stamp: CeramicCache) -> CeramicCache:
    v2_stamp_response = requests.post(
        settings.CERAMIC_CACHE_CONVERT_STAMP_TO_V2_URL, json=v1_stamp.stamp
    )

    if v2_stamp_response.status_code == 200:
        v2_stamp = CeramicCache(
            type=CeramicCache.StampType.V2,
            address=v1_stamp.address,
            provider=v1_stamp.provider,
            created_at=v1_stamp.created_at,
            updated_at=v1_stamp.updated_at,
            stamp=v2_stamp_response.json(),
        )
        v2_stamp.save()
        return v2_stamp
    else:
        log.error(
            "Error converting stamp to V2: %s: %s",
            v2_stamp_response.status_code,
            v2_stamp_response.text,
            exc_info=True,
        )

    return None


def get_passport_state(address: str) -> list[CeramicCache]:
    v1_stamp_list = CeramicCache.objects.filter(
        type=CeramicCache.StampType.V1, address=address, deleted_at__isnull=True
    )

    v2_stamps = {
        c.provider: c
        for c in CeramicCache.objects.filter(
            type=CeramicCache.StampType.V2, address=address, deleted_at__isnull=True
        )
    }

    # We want to make sure that all stamps in v1_stamps are also in v2_stamps, and that no
    # v1_stamp is newer than it's equivalent in v2_stamps
    for v1_stamp in v1_stamp_list:
        if v1_stamp.provider not in v2_stamps:
            # the v1 stamp is missing in v2_stamps, so we need to create that entry
            v2_stamp = migrate_stamp_to_v2(v1_stamp)
            if v2_stamp:
                v2_stamps[v2_stamp.provider] = v2_stamp

    # There is also the edge case wher where the V1 stamp is not identical to the V2 stamp
    # (for example V1 stamp expires after the v2 stamp)
    # But we ignore this, as it can only occur if for some reason we are rolling back the passport app.
    # This case cannot occur normally

    return v2_stamps.values()


@router.post("stamps/bulk", response={201: GetStampResponse}, auth=JWTDidAuth())
def cache_stamps(request, payload: List[CacheStampPayload]):
    try:
        address = get_address_from_did(request.did)
        return handle_add_stamps(address, payload)
    except Exception as e:
        raise e


def handle_add_stamps(address: str, payload: List[CacheStampPayload]):
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    now = get_utc_time()

    existing_stamps = CeramicCache.objects.filter(
        address=address,
        provider__in=[p.provider for p in payload],
        deleted_at__isnull=True,
    )

    existing_stamps.update(updated_at=now, deleted_at=now)

    new_stamp_objects = [
        CeramicCache(
            type=CeramicCache.StampType.V2,
            address=address,
            provider=p.provider,
            stamp=p.stamp,
            updated_at=now,
        )
        for p in payload
    ]

    CeramicCache.objects.bulk_create(new_stamp_objects)

    updated_passport_state = get_passport_state(address)

    return GetStampsWithScoreResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=stamp.address, provider=stamp.provider, stamp=stamp.stamp
            )
            for stamp in updated_passport_state
        ],
        score=get_detailed_score_response_for_address(address),
    )


@router.patch("stamps/bulk", response={200: GetStampResponse}, auth=JWTDidAuth())
def patch_stamps(request, payload: List[CacheStampPayload]):
    try:
        address = get_address_from_did(request.did)
        return handle_patch_stamps(address, payload)

    except Exception as e:
        log.error(
            "Failed patch_stamps request: '%s'",
            [p.dict() for p in payload],
            exc_info=True,
        )
        raise InternalServerException()


def handle_patch_stamps(address: str, payload: List[CacheStampPayload]):
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    now = get_utc_time()

    # Soft delete all, the ones with a stamp defined will be re-created
    providers_to_delete = [p.provider for p in payload]

    if providers_to_delete:
        stamps = CeramicCache.objects.filter(
            address=address,
            provider__in=providers_to_delete,
            deleted_at__isnull=True,
            # We do not specify type because we delete both V1 and V2 stamps
        )
        stamps.update(updated_at=now, deleted_at=now)

    new_stamp_objects = [
        CeramicCache(
            type=CeramicCache.StampType.V2,
            address=address,
            provider=p.provider,
            stamp=p.stamp,
            updated_at=now,
        )
        for p in payload
        if p.stamp
    ]

    if new_stamp_objects:
        CeramicCache.objects.bulk_create(new_stamp_objects)

    updated_passport_state = get_passport_state(address)

    return GetStampsWithScoreResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=stamp.address, provider=stamp.provider, stamp=stamp.stamp
            )
            for stamp in updated_passport_state
        ],
        score=get_detailed_score_response_for_address(address),
    )


@router.delete("stamps/bulk", response=GetStampResponse, auth=JWTDidAuth())
def delete_stamps(request, payload: List[DeleteStampPayload]):
    try:
        address = get_address_from_did(request.did)
        return handle_delete_stamps(address, payload)
    except Exception as e:
        raise e


def handle_delete_stamps(address: str, payload: List[DeleteStampPayload]):
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    stamps = CeramicCache.objects.filter(
        # We do not filter by type. The thinking is: if a user wants to delete a V2 stamp, then he wants to delete both the V1 and V2 stamps.
        # Otherwise the `get_passport_state` function will re-create the V2 stamp from it's V2 version
        address=address,
        provider__in=[p.provider for p in payload],
        deleted_at__isnull=True,
    )
    if not stamps:
        raise InvalidDeleteCacheRequestException()

    now = get_utc_time()
    stamps.update(deleted_at=now, updated_at=now)

    updated_passport_state = get_passport_state(address)

    return GetStampsWithScoreResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=stamp.address, provider=stamp.provider, stamp=stamp.stamp
            )
            for stamp in updated_passport_state
        ],
        score=get_detailed_score_response_for_address(address),
    )


@router.get("weights", response=Dict[str, str])
def get_scorer_weights(request):
    return handle_get_scorer_weights()


@router.get("stamp", response=GetStampResponse)
def get_stamps(request, address):
    try:
        return handle_get_stamps(address)
    except Exception as e:
        raise e


def handle_get_stamps(address: str):
    stamps = get_passport_state(address)

    scorer_id = settings.CERAMIC_CACHE_SCORER_ID
    if (
        scorer_id
        and not Score.objects.filter(
            passport__address=address.lower(),
            passport__community_id=scorer_id,
        ).exists()
    ):
        get_detailed_score_response_for_address(address)

    return GetStampResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=stamp.address, provider=stamp.provider, stamp=stamp.stamp
            )
            for stamp in stamps
        ],
    )


@router.get(
    "/score/{str:address}",
    response=DetailedScoreResponse,
    auth=JWTDidAuth(),
)
def get_score(request, address: str) -> DetailedScoreResponse:
    return get_score_v1(request, address)


@router.post(
    "/score/{str:address}",
    response=DetailedScoreResponse,
    auth=JWTDidAuth(),
)
def calc_score(request, address: str) -> DetailedScoreResponse:
    return get_detailed_score_response_for_address(address)


@router.post(
    "authenticate",
    response=AccessTokenResponse,
)
def authenticate(request, payload: CacaoVerifySubmit):
    return authenticate_v1(request, payload)
