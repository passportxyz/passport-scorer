from typing import List

from django.conf import settings
from ninja import Router
from ninja_extra import NinjaExtraAPI
from ninja_extra.exceptions import APIException

import api_logging as logging
from ceramic_cache.api.v1 import handle_get_ui_score
from ceramic_cache.exceptions import InternalServerException, TooManyStampsException
from ceramic_cache.models import Ban, Revocation
from cgrants.api import (
    ContributorStatistics,
    handle_get_contributor_statistics,
)
from registry.api.schema import DetailedScoreResponse
from registry.api.utils import is_valid_address
from registry.exceptions import InvalidAddressException
from stake.api import handle_get_gtc_stake
from stake.schema import ErrorMessageResponse, StakeResponse
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


@api_router.get(
    "/stake/gtc/{str:address}",
    auth=internal_api_key,
    response={
        200: StakeResponse,
        400: ErrorMessageResponse,
    },
    summary="Retrieve GTC stake amounts for the GTC Staking stamp",
    description="Get self and community GTC stakes for an address",
)
def get_gtc_stake(request, address: str) -> StakeResponse:
    """
    Get relevant GTC stakes for an address
    """
    if not is_valid_address(address):
        raise InvalidAddressException()

    get_stake_response = handle_get_gtc_stake(address)
    response = StakeResponse(items=get_stake_response)
    return response


@api_router.get(
    "/cgrants/contributor_statistics",
    response=ContributorStatistics,
    auth=internal_api_key,
)
def cgrants_contributor_statistics(request, address: str):
    return handle_get_contributor_statistics(address)


@api_router.get(
    "/score/{int:scorer_id}/{str:address}",
    response=DetailedScoreResponse,
    auth=internal_api_key,
)
def calc_score_community(
    request,
    scorer_id: int,
    address: str,
) -> DetailedScoreResponse:
    return handle_get_ui_score(address, scorer_id)
