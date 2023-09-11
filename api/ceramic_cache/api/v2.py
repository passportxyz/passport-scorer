"""Ceramic Cache API"""

from typing import List

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
    JWTDidAuth,
)
from .v1 import authenticate as authenticate_v1
from .v1 import get_address_from_did
from .v1 import get_score as get_score_v1
from .v1 import get_utc_time, submit_passport_from_cache

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
        type=CeramicCache.StampType.V1, address=address
    )

    v2_stamps = {
        c.provider: c
        for c in CeramicCache.objects.filter(
            type=CeramicCache.StampType.V2, address=address
        )
    }

    # We want to make sure that all stamps in v2_stamps are also in v1_stamps, and that no
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
        if len(payload) > settings.MAX_BULK_CACHE_SIZE:
            raise TooManyStampsException()

        address = get_address_from_did(request.did)
        stamp_objects = []
        now = get_utc_time()
        for p in payload:
            stamp_object = CeramicCache(
                type=CeramicCache.StampType.V2,
                address=address,
                provider=p.provider,
                stamp=p.stamp,
                updated_at=now,
            )
            stamp_objects.append(stamp_object)

        created = CeramicCache.objects.bulk_create(
            stamp_objects,
            update_conflicts=True,
            update_fields=["stamp", "updated_at"],
            unique_fields=["type", "address", "provider"],
        )

        submit_passport_from_cache(address)

        updated_passport_state = get_passport_state(address)

        return GetStampResponse(
            success=True,
            stamps=[
                CachedStampResponse(
                    address=stamp.address, provider=stamp.provider, stamp=stamp.stamp
                )
                for stamp in updated_passport_state
            ],
        )

    except Exception as e:
        raise e


@router.patch("stamps/bulk", response={200: GetStampResponse}, auth=JWTDidAuth())
def patch_stamps(request, payload: List[CacheStampPayload]):
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    try:
        address = get_address_from_did(request.did)
        stamp_objects = []
        providers_to_delete = []
        updated = []
        now = get_utc_time()

        for p in payload:
            if p.stamp:
                stamp_object = CeramicCache(
                    type=CeramicCache.StampType.V2,
                    address=address,
                    provider=p.provider,
                    stamp=p.stamp,
                    updated_at=now,
                )
                stamp_objects.append(stamp_object)
            else:
                providers_to_delete.append(p.provider)

        if stamp_objects:
            updated = CeramicCache.objects.bulk_create(
                stamp_objects,
                update_conflicts=True,
                update_fields=["stamp", "updated_at"],
                unique_fields=["type", "address", "provider"],
            )

        if providers_to_delete:
            stamps = CeramicCache.objects.filter(
                address=address,
                provider__in=providers_to_delete,
                type=CeramicCache.StampType.V2,
            )
            stamps.delete()

        submit_passport_from_cache(address)

        updated_passport_state = get_passport_state(address)

        return GetStampResponse(
            success=True,
            stamps=[
                CachedStampResponse(
                    address=stamp.address, provider=stamp.provider, stamp=stamp.stamp
                )
                for stamp in updated_passport_state
            ],
        )

    except Exception as e:
        log.error(
            "Failed patch_stamps request: '%s'",
            [p.dict() for p in payload],
            exc_info=True,
        )
        raise InternalServerException()


@router.delete("stamps/bulk", response=GetStampResponse, auth=JWTDidAuth())
def delete_stamps(request, payload: List[DeleteStampPayload]):
    try:
        if len(payload) > settings.MAX_BULK_CACHE_SIZE:
            raise TooManyStampsException()

        address = get_address_from_did(request.did)
        stamps = CeramicCache.objects.filter(
            type=CeramicCache.StampType.V2,
            address=address,
            provider__in=[p.provider for p in payload],
        )
        if not stamps:
            raise InvalidDeleteCacheRequestException()
        stamps.delete()

        submit_passport_from_cache(address)

        updated_passport_state = get_passport_state(address)

        return GetStampResponse(
            success=True,
            stamps=[
                CachedStampResponse(
                    address=stamp.address, provider=stamp.provider, stamp=stamp.stamp
                )
                for stamp in updated_passport_state
            ],
        )
    except Exception as e:
        raise e


@router.get("stamp", response=GetStampResponse)
def get_stamps(request, address):
    try:
        stamps = get_passport_state(address)

        scorer_id = settings.CERAMIC_CACHE_SCORER_ID
        if (
            scorer_id
            and not Score.objects.filter(
                passport__address=address.lower(),
                passport__community_id=scorer_id,
            ).exists()
        ):
            submit_passport_from_cache(address)

        return GetStampResponse(
            success=True,
            stamps=[
                CachedStampResponse(
                    address=stamp.address, provider=stamp.provider, stamp=stamp.stamp
                )
                for stamp in stamps
            ],
        )
    except Exception as e:
        raise e


@router.get(
    "/score/{str:address}",
    response=DetailedScoreResponse,
    auth=JWTDidAuth(),
)
def get_score(request, address: str) -> DetailedScoreResponse:
    return get_score_v1(request, address)


@router.post(
    "authenticate",
    response=AccessTokenResponse,
)
def authenticate(request, payload: CacaoVerifySubmit):
    return authenticate_v1(request, payload)
