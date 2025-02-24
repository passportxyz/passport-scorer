from typing import List

from django.conf import settings
from ninja_extra.exceptions import APIException

import api_logging as logging
from ceramic_cache.exceptions import InternalServerException, TooManyStampsException
from ceramic_cache.models import Ban, Revocation

from .exceptions import InvalidBanQueryException
from .schema import (
    CheckBanResult,
    Credential,
    RevocationCheckPayload,
    RevocationCheckResponse,
)

log = logging.getLogger(__name__)


def handle_check_bans(payload: List[Credential]) -> List[CheckBanResult]:
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


def handle_check_revocations(
    payload: RevocationCheckPayload,
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
