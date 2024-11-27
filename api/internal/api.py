from typing import Any, List

from django.conf import settings
from ninja import Router, Schema
from ninja_extra import NinjaExtraAPI
from ninja_extra.exceptions import APIException

import api_logging as logging
from ceramic_cache.api.schema import (
    CacheStampPayload,
    GetStampsWithScoreResponse,
)
from ceramic_cache.api.v1 import handle_add_stamps
from ceramic_cache.exceptions import InternalServerException, TooManyStampsException
from ceramic_cache.models import Ban, Revocation
from registry.api.schema import (
    ErrorMessageResponse,
)
from registry.api.utils import (
    is_valid_address,
)
from registry.exceptions import (
    InvalidAddressException,
)
from trusta_labs.api import CgrantsApiKey

from .exceptions import InvalidBanQueryException
from .schema import (
    CheckBanResult,
    Credential,
    RevocationCheckPayload,
    RevocationCheckResponse,
)

api_router = Router()

api = NinjaExtraAPI(
    urls_namespace="internal",
    title="Internal API",
    description="Endpoints for internal use.",
)


api.add_router("", api_router)

log = logging.getLogger(__name__)


internal_api_key = CgrantsApiKey()


class AddStampsPayload(Schema):
    scorer_id: int
    stamps: List[Any]


@api_router.post(
    "/stamps/{str:address}",
    auth=internal_api_key,
    response={
        200: GetStampsWithScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Add Stamps and get the new score",
)
def add_stamps(
    request, address: str, payload: AddStampsPayload
) -> GetStampsWithScoreResponse:
    address_lower = address.lower()
    if not is_valid_address(address_lower):
        raise InvalidAddressException()

    cacheStampPayloads = [
        CacheStampPayload(
            address=address_lower,
            provider=stamp.get("credentialSubject", {}).get("provider"),
            stamp=stamp,
        )
        for stamp in payload.stamps
    ]

    return handle_add_stamps(address, cacheStampPayloads, payload.scorer_id)


@api_router.post("/check-bans", response=List[CheckBanResult], auth=internal_api_key)
def check_bans(request, payload: List[Credential]) -> List[CheckBanResult]:
    """
    Check for active bans matching the given address and/or hashes.
    Returns list of relevant active bans.
    """
    unique_ids = list(set([c.credentialSubject.id for c in payload]))

    if len(unique_ids) < 1:
        raise InvalidBanQueryException("Must provide valid credential(s)")

    if len(unique_ids) > 1:
        raise InvalidBanQueryException(
            "All credentials must be issued to the same address"
        )

    address = unique_ids[0].split(":")[-1]

    hashes = list(
        set([c.credentialSubject.hash for c in payload if c.credentialSubject.hash])
    )

    try:
        bans = Ban.get_bans(address=address, hashes=hashes)

        credential_ban_results = [
            Ban.check_bans_for(
                bans, address, c.credentialSubject.hash, c.credentialSubject.provider
            )
            for c in payload
        ]

        return [
            CheckBanResult(
                hash=c.credentialSubject.hash,
                is_banned=is_banned,
                ban_type=ban_type,
                end_time=ban.end_time if ban else None,
                reason=ban.reason if ban else None,
            )
            for c, (is_banned, ban_type, ban) in zip(payload, credential_ban_results)
        ]

    except APIException:
        # re-raise API exceptions
        raise
    except Exception as e:
        log.error("Failed to check bans", exc_info=True)
        raise InternalServerException("Failed to check bans") from e


@api_router.post(
    "/check-revocations", response=List[RevocationCheckResponse], auth=internal_api_key
)
def check_revocations(
    request, payload: RevocationCheckPayload
) -> List[RevocationCheckResponse]:
    """
    Check if stamps with given proof values have been revoked.
    Returns revocation status for each proof value.
    """
    if len(payload.proof_values) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    try:
        # Query for revocations matching any of the proof values
        revoked_proof_values = set(
            Revocation.objects.filter(proof_value__in=payload.proof_values).values_list(
                "proof_value", flat=True
            )
        )

        # Return status for each requested proof value
        return [
            RevocationCheckResponse(
                proof_value=proof_value, is_revoked=proof_value in revoked_proof_values
            )
            for proof_value in payload.proof_values
        ]

    except APIException:
        # re-raise API exceptions
        raise
    except Exception as e:
        log.error("Failed to check revocations", exc_info=True)
        raise InternalServerException("Failed to check revocations") from e
