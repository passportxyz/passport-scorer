import logging
from decimal import Decimal
from typing import List, Optional

# --- Deduplication Modules
from account.models import AccountAPIKey, Community, Nonce
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.pagination import paginate
from ninja.security import APIKeyHeader
from registry.models import Passport, Score
from registry.utils import get_signer, get_signing_message

from .exceptions import (
    InvalidCommunityScoreRequestException,
    InvalidNonceException,
    InvalidSignerException,
    InvalidLimitException,
    Unauthorized,
)
from .tasks import score_passport

log = logging.getLogger(__name__)
# api = NinjaExtraAPI(urls_namespace="registry")
router = Router()


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
    address: str
    score: Optional[str]
    status: Optional[str]
    last_score_timestamp: Optional[str]
    evidence: Optional[ThresholdScoreEvidenceResponse]
    error: Optional[str]

    @staticmethod
    def resolve_last_score_timestamp(obj):
        if obj.last_score_timestamp:
            return obj.last_score_timestamp.isoformat()
        return None

    @staticmethod
    def resolve_address(obj):
        return obj.passport.address


class GetScoresResponse(Schema):
    items: List[DetailedScoreResponse]
    count: int


class SimpleScoreResponse(Schema):
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
def signing_message(_request) -> SigningMessageResponse:
    nonce = Nonce.create_nonce().nonce
    return {
        "message": get_signing_message(nonce),
        "nonce": nonce,
    }


# TODO define logic once Community model has been updated
def community_requires_signature(_):
    return False


@router.post("/submit-passport", auth=ApiKey(), response=DetailedScoreResponse)
def submit_passport(
    request, payload: SubmitPassportPayload
) -> List[DetailedScoreResponse]:
    # TODO: gerald - test that checksummed & non-checksummed addresses work
    address_lower = payload.address.lower()

    # Get DID from address
    # did = get_did(payload.address)
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

    # Create an empty passport instance, only needed to be able to create a pending Score
    # The passport will be updated by the score_passport task
    db_passport, _ = Passport.objects.update_or_create(
        address=payload.address.lower(),
        community=user_community,
        defaults={
            "passport": {},  # Leave the dict empty for now
        },
    )

    # Create a score with status PROCESSING
    score, _ = Score.objects.update_or_create(
        passport_id=db_passport.id,
        defaults=dict(score=None, status=Score.Status.PROCESSING),
    )

    score_passport.delay(user_community.id, payload.address)

    return DetailedScoreResponse(
        address=score.passport.address,
        score=score.score,
        status=score.status,
        evidence=score.evidence,
        last_score_timestamp=score.last_score_timestamp.isoformat()
        if score.last_score_timestamp
        else None,
    )


@router.get(
    "/score/{int:community_id}/{str:address}",
    auth=ApiKey(),
    response=DetailedScoreResponse,
)
def get_score(request, address: str, community_id: int) -> DetailedScoreResponse:
    try:
        # TODO: validate that community belongs to the account holding the ApiKey
        lower_address = address.lower()
        community = Community.objects.get(id=community_id)
        passport = Passport.objects.get(address=lower_address, community=community)
        score = Score.objects.get(passport=passport)
        return score
    except Exception as e:
        log.error(
            "Error getting passport scores. community_id=%s",
            community_id,
            exc_info=True,
        )
        raise InvalidCommunityScoreRequestException()


@router.get("/score/{int:community_id}", auth=ApiKey(), response=List[DetailedScoreResponse])
@paginate(pass_parameter="pagination_info")
def get_scores(
    request, community_id: int, address: str = "", **kwargs
) -> List[DetailedScoreResponse]:

    if kwargs["pagination_info"].limit > 1000:
        raise InvalidLimitException()

    try:
        # Get community object
        if request.user.groups.filter(name="Researcher").exists():
            user_community = get_object_or_404(Community, id=community_id)
        else:
            user_community = get_object_or_404(
                Community, id=community_id, account=request.auth
            )
        scores = Score.objects.filter(passport__community__id=user_community.id).prefetch_related(
            "passport"
        )

        if address:
            scores = scores.filter(passport__address=address.lower())

        return scores

    except Exception as e:
        log.error(
            "Error getting passport scores. community_id=%s",
            community_id,
            exc_info=True,
        )
        raise InvalidCommunityScoreRequestException()


@router.get(
    "/score/", auth=ApiKey(), response=List[DetailedScoreResponse]
)
@paginate()
def get_scores(request) -> List[DetailedScoreResponse]:
    try:        
        if not request.user.groups.filter(name="Researcher").exists():
            return 403, { "detail": "You are not allowed to access this endpoint"}

        scores = Score.objects.all()

        return [
            DetailedScoreResponse(
                address=score.passport.address,
                score=score.score,
                status=score.status,
                evidence=score.evidence,
                last_score_timestamp=score.last_score_timestamp.isoformat()
                if score.last_score_timestamp
                else None,
                error=score.error,
            )
            for score in scores
        ]

    except Exception as e:
        log.error("Error getting passport scores.")
        raise InvalidCommunityScoreRequestException()
