import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Union

# --- Deduplication Modules
from account.deduplication.lifo import lifo
from account.models import AccountAPIKey, Community, Nonce
from asgiref.sync import async_to_sync
from django.shortcuts import get_object_or_404
from ninja import Field, Query, Router
from ninja.pagination import paginate
from ninja.security import APIKeyHeader
from ninja_extra import NinjaExtraAPI, status
from ninja_extra.exceptions import APIException
from ninja_schema import Schema
from reader.passport_reader import get_did, get_passport
from registry.models import Passport, Score, Stamp
from registry.utils import (
    get_signer,
    get_signing_message,
    validate_credential,
    verify_issuer,
)

log = logging.getLogger(__name__)
# api = NinjaExtraAPI(urls_namespace="registry")
router = Router()


class InvalidSignerException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Address does not match signature."


class InvalidNonceException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid nonce."


class InvalidPassportCreationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Error Creating Passport."


class InvalidScoreRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to get score for provided address(s)."


class InvalidCommunityScoreRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to get score for provided community."


class NoPassportException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No Passport found for this address."


class Unauthorized(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid API Key."


class SubmitPassportPayload(Schema):
    address: str
    community: str  # TODO: gerald: community_id ???, and make it int
    signature: str = ""
    nonce: str = ""


class ScoreEvidenceResponse(Schema):
    type: str
    success: bool


class ThresholdScoreEvidenceResponse(ScoreEvidenceResponse):
    rawScore: Decimal
    threshold: Decimal


class DetailedScoreResponse(Schema):
    # passport_id: int
    address: str
    score: str
    evidence: Optional[List[ThresholdScoreEvidenceResponse]]


class SimpleScoreResponse(Schema):
    # passport_id: int
    address: str
    score: Decimal  # The score should be represented as string as it will be a decimal number


class SigningMessageResponse(Schema):
    message: str
    nonce: str


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            raise Unauthorized()
        try:
            key = request.META["HTTP_AUTHORIZATION"].split()[1]
            api_key = AccountAPIKey.objects.get_from_key(key)

            user_account = api_key.account

            if user_account:
                return user_account
        except AccountAPIKey.DoesNotExist:
            raise Unauthorized()


@router.get("/signing-message", auth=ApiKey(), response=SigningMessageResponse)
def signing_message() -> SigningMessageResponse:
    nonce = Nonce.create_nonce().nonce
    return {
        "message": get_signing_message(nonce),
        "nonce": nonce,
    }


# TODO define logic once Community model has been updated
def community_requires_signature(_):
    return False


@router.post("/submit-passport", auth=ApiKey(), response=List[DetailedScoreResponse])
def submit_passport(
    request, payload: SubmitPassportPayload
) -> List[DetailedScoreResponse]:
    # TODO: gerald - test that checksummed & non-checksummed addresses work
    address_lower = payload.address.lower()

    # Get DID from address
    did = get_did(payload.address)
    log.debug("/submit-passport, payload=%s", payload)

    # Get community object
    user_community = get_object_or_404(
        Community, id=payload.community, account=request.auth
    )

    # Verify the signer
    # TODO This first condition--payload.signature--is only here for testing and
    # can be removed when community_requires_signature() is completed
    if payload.signature or community_requires_signature(user_community):
        if get_signer(payload.nonce, payload.signature).lower() != address_lower:
            raise InvalidSignerException()

        # Verify nonce
        if not Nonce.use_nonce(payload.nonce):
            log.error("Invalid nonce %s for address %s", payload.nonce, payload.address)
            raise InvalidNonceException()

    log.debug("Getting passport")
    # Passport contents read from ceramic
    passport = get_passport(did)

    if not passport:
        raise NoPassportException()

    try:
        log.debug("deduplicating ...")
        # Check if stamp(s) with hash already exist and remove it/them from the incoming passport
        passport_to_be_saved = lifo(passport, address_lower)

        # Save passport to Passport database (related to community by community_id)
        db_passport, _ = Passport.objects.update_or_create(
            address=payload.address.lower(),
            community=user_community,
            defaults={
                "passport": passport_to_be_saved,
            },
        )

        log.debug("validating stamps")
        for stamp in passport_to_be_saved["stamps"]:
            stamp_return_errors = async_to_sync(validate_credential)(
                did, stamp["credential"]
            )
            try:
                # TODO: use some library or https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat to
                # parse iso timestamps
                stamp_expiration_date = datetime.strptime(
                    stamp["credential"]["expirationDate"], "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            except ValueError:
                stamp_expiration_date = datetime.strptime(
                    stamp["credential"]["expirationDate"], "%Y-%m-%dT%H:%M:%SZ"
                )

            is_issuer_verified = verify_issuer(stamp)
            # check that expiration date is not in the past
            stamp_is_expired = stamp_expiration_date < datetime.now()
            if (
                len(stamp_return_errors) == 0
                and not stamp_is_expired
                and is_issuer_verified
            ):
                Stamp.objects.update_or_create(
                    hash=stamp["credential"]["credentialSubject"]["hash"],
                    passport=db_passport,
                    defaults={
                        "provider": stamp["provider"],
                        "credential": stamp["credential"],
                    },
                )
            else:
                log.debug(
                    "Stamp not created. Stamp=%s\nReason: errors=%s stamp_is_expired=%s is_issuer_verified=%s",
                    stamp,
                    stamp_return_errors,
                    stamp_is_expired,
                    is_issuer_verified,
                )

        log.debug("Saving score")
        scorer = user_community.get_scorer()
        scores = scorer.compute_score([db_passport.id])

        scoreData = scores[0]

        score, _ = Score.objects.update_or_create(
            passport_id=db_passport.id, defaults=dict(score=scoreData.score)
        )

        # We return an array of results here, because in some cases we might have scorers (like the APU scoe)
        # that will affect also the score of other passwords (as scores are relative)
        # We return decimal for all scorers (Weighted and Binary Weighted) atm
        return [
            DetailedScoreResponse(
                # passport_id= score.passport.id,
                address=score.passport.address,
                score=Score.objects.get(
                    pk=score.id
                ).score,  # Just reading out the value from DB to have it as decimal formatted
                evidence=scoreData.evidence,
            )
        ]
    except Exception:
        log.error(
            "Error when handling passport submission. payload=%s",
            payload,
            exc_info=True,
        )
        raise InvalidPassportCreationException()


@router.get(
    "/score/{int:community_id}/{str:address}",
    auth=ApiKey(),
    response=SimpleScoreResponse,
)
def get_score(request, address: str, community_id: int) -> DetailedScoreResponse:
    try:
        score = Score.objects.get(
            passport__address=address, passport__community__id=community_id
        )

        return {
            "address": score.passport.address,
            "score": score.score,
        }
    except Exception as e:

        log.error(
            "Error when getting passport score. address=%s, community_id=%s",
            address,
            community_id,
            exc_info=True,
        )
        raise InvalidScoreRequestException()


@router.get(
    "/scores/{int:community_id}", auth=ApiKey(), response=List[DetailedScoreResponse]
)
@paginate()
def get_scores(request, community_id: int, **kwargs) -> List[DetailedScoreResponse]:
    try:
        # Get community object
        user_community = get_object_or_404(
            Community, id=community_id, account=request.auth
        )

        scores = Score.objects.filter(passport__community__id=user_community.id)

        return [{"address": s.passport.address, "score": s.score} for s in scores]
    except Exception as e:
        log.error(
            "Error getting passport scores. community_id=%s",
            community_id,
            exc_info=True,
        )
        raise InvalidCommunityScoreRequestException()
