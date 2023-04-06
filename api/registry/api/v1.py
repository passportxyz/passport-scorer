import logging
from decimal import Decimal
from enum import Enum
from typing import List, Optional

# --- Deduplication Modules
from account.models import AccountAPIKey, Community, Nonce
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.module_loading import import_string
from django_ratelimit.core import is_ratelimited
from django_ratelimit.decorators import ALL
from django_ratelimit.exceptions import Ratelimited
from ninja import Router, Schema
from ninja.pagination import paginate
from ninja.security import APIKeyHeader
from registry.models import Passport, Score, Stamp
from registry.permissions import ResearcherPermission
from registry.utils import (
    decode_cursor,
    encode_cursor,
    get_signer,
    get_signing_message,
    permissions_required,
    reverse_lazy_with_query,
)

from ..exceptions import (
    InvalidCommunityScoreRequestException,
    InvalidLimitException,
    InvalidNonceException,
    InvalidScorerIdException,
    InvalidSignerException,
    Unauthorized,
    api_get_object_or_404,
)
from ..tasks import score_passport

log = logging.getLogger(__name__)
# api = NinjaExtraAPI(urls_namespace="registry")
router = Router()

analytics_router = Router()


class SubmitPassportPayload(Schema):
    address: str
    community: str = "Deprecated"
    scorer_id: str = ""
    signature: str = ""
    nonce: str = ""


class ScoreEvidenceResponse(Schema):
    type: str
    success: bool


class ThresholdScoreEvidenceResponse(ScoreEvidenceResponse):
    rawScore: Decimal
    threshold: Decimal


class StatusEnum(str, Enum):
    processing = Score.Status.PROCESSING
    error = Score.Status.ERROR
    done = Score.Status.DONE


class StampCredentialResponse(Schema):
    version: str
    credential: dict


class CursorPaginatedStampCredentialResponse(Schema):
    next: Optional[str]
    prev: Optional[str]
    items: List[StampCredentialResponse]


class DetailedScoreResponse(Schema):
    address: str
    score: Optional[str]
    status: Optional[StatusEnum]
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


class CursorPaginatedScoreResponse(Schema):
    next: Optional[str]
    prev: Optional[str]
    items: List[DetailedScoreResponse]


class SimpleScoreResponse(Schema):
    address: str
    score: Decimal  # The score should be represented as string as it will be a decimal number


class SigningMessageResponse(Schema):
    message: str
    nonce: str


class ErrorMessageResponse(Schema):
    detail: str


def check_rate_limit(request):
    """
    Check the rate limit for the API.
    This is based on the original ratelimit decorator from django_ratelimit
    """
    old_limited = getattr(request, "limited", False)
    rate = request.api_key.rate_limit
    ratelimited = is_ratelimited(
        request=request,
        group="registry",
        fn=None,
        key=lambda _request, _group: request.api_key.prefix,
        rate=rate,
        method=ALL,
        increment=True,
    )
    request.limited = ratelimited or old_limited
    if ratelimited:
        cls = getattr(settings, "RATELIMIT_EXCEPTION_CLASS", Ratelimited)
        raise (import_string(cls) if isinstance(cls, str) else cls)()


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        """
        The authenticate method will validate the API key:
        1. first in the X-API-Key header - this will have preceedence
        2. in the HTTP_AUTHORIZATION header if none exists in the X-API-Key header (this is for backwards compatibility)
        """
        if not key:
            # if X-API-Key was not specified in the header read the HTTP_AUTHORIZATION
            # and try to load the tey from there
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if not auth_header:
                raise Unauthorized()

            try:
                key = auth_header.split()[1]
            except:
                raise Unauthorized()

        try:
            api_key = AccountAPIKey.objects.get_from_key(key)
            request.api_key = api_key
            user_account = api_key.account
            if user_account:
                request.user = user_account.user
                return user_account
        except AccountAPIKey.DoesNotExist:
            raise Unauthorized()


@router.get(
    "/signing-message",
    auth=ApiKey(),
    response={
        200: SigningMessageResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
    },
    summary="Submit passport for scoring",
    description="""Use this API to get a message to sign and a nonce to use when submitting your passport for scoring.""",
)
def signing_message(request) -> SigningMessageResponse:
    check_rate_limit(request)
    nonce = Nonce.create_nonce().nonce
    return {
        "message": get_signing_message(nonce),
        "nonce": nonce,
    }


# TODO define logic once Community model has been updated
def community_requires_signature(_):
    return False


def get_scorer_id(payload: SubmitPassportPayload) -> str:
    scorer_id = ""
    if payload.scorer_id:
        scorer_id = payload.scorer_id
    elif payload.community and payload.community != "Deprecated":
        scorer_id = payload.community
    else:
        raise InvalidScorerIdException()

    return scorer_id


@router.post(
    "/submit-passport",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Submit passport for scoring",
    description="""Use this API to submit your passport for scoring.\n
This API will return a `DetailedScoreResponse` structure with status **PROCESSING** immediatly while your passport is being pulled from storage and the scoring algorithm is run.\n
You need to check for the status of the operation by calling the `/score/{int:scorer_id}/{str:address}` API. The operation will have finished when the status returned is **DONE**
""",
)
def submit_passport(request, payload: SubmitPassportPayload) -> DetailedScoreResponse:
    check_rate_limit(request)
    address_lower = payload.address.lower()

    # Get DID from address
    # did = get_did(payload.address)
    log.debug("/submit-passport, payload=%s", payload)

    try:
        scorer_id = get_scorer_id(payload)
    except Exception as e:
        raise e

    # Get community object
    user_community = get_object_or_404(Community, id=scorer_id, account=request.auth)

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
    "/score/{int:scorer_id}/{str:address}",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Get score for an address that is associated with a scorer",
    description="""Use this endpoint to fetch the score for a specific address that is associated with a scorer\n
This endpoint will return a `DetailedScoreResponse`. This endpoint will also return the status of the asynchronous operation that was initiated with a request to the `/submit-passport` API.\n
""",
)
def get_score(request, address: str, scorer_id: int) -> DetailedScoreResponse:
    check_rate_limit(request)

    # Get community object
    user_community = api_get_object_or_404(
        Community, id=scorer_id, account=request.auth
    )

    try:
        lower_address = address.lower()

        score = Score.objects.get(
            passport__address=lower_address, passport__community=user_community
        )
        return score
    except Exception as e:
        log.error(
            "Error getting passport scores. scorer_id=%s",
            scorer_id,
            exc_info=True,
        )
        raise InvalidCommunityScoreRequestException() from e


@router.get(
    "/score/{int:scorer_id}",
    auth=ApiKey(),
    response={
        200: List[DetailedScoreResponse],
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Get scores for all addresses that are associated with a scorer",
    description="""Use this endpoint to fetch the scores for all addresses that are associated with a scorer\n
This API will return a list of `DetailedScoreResponse` objects. The endpoint supports pagination and will return a maximum of 1000 scores per request.\n
Pass a limit and offset query parameter to paginate the results. For example: `/score/1?limit=100&offset=100` will return the second page of 100 scores.\n
""",
)
@paginate(pass_parameter="pagination_info")
def get_scores(
    request, scorer_id: int, address: str = "", **kwargs
) -> List[DetailedScoreResponse]:
    check_rate_limit(request)
    if kwargs["pagination_info"].limit > 1000:
        raise InvalidLimitException()

    # Get community object
    user_community = api_get_object_or_404(
        Community, id=scorer_id, account=request.auth
    )

    try:
        scores = Score.objects.filter(
            passport__community__id=user_community.id
        ).select_related("passport")

        if address:
            scores = scores.filter(passport__address=address.lower())

        return scores

    except Exception as e:
        log.error(
            "Error getting passport scores. scorer_id=%s",
            scorer_id,
            exc_info=True,
        )
        raise e


@router.get(
    "/stamps/{str:address}",
    auth=ApiKey(),
    response={
        200: CursorPaginatedStampCredentialResponse,
        400: ErrorMessageResponse,
        401: ErrorMessageResponse,
    },
    summary="Get passport for an address",
    description="""Use this endpoint to fetch the passport for a specific address\n
This endpoint will return a `CursorPaginatedStampCredentialResponse`.\n
""",
)
def get_passport_stamps(
    request, address: str, token: str = None, limit: int = 1000
) -> CursorPaginatedStampCredentialResponse:
    check_rate_limit(request)

    if limit > 1000:
        raise InvalidLimitException()

    # ref: https://medium.com/swlh/how-to-implement-cursor-pagination-like-a-pro-513140b65f32

    query = (
        Stamp.objects.order_by("-id")
        .filter(passport__address=address.lower())
        .select_related("passport")
    )

    direction, id = decode_cursor(token) if token else (None, None)

    if direction == "next":
        # note we use lt here because we're querying in descending order
        stamps = list(query.filter(id__lt=id)[:limit])

    elif direction == "prev":
        stamps = list(query.filter(id__gt=id).order_by("id")[:limit])
        stamps.reverse()

    else:
        stamps = list(query[:limit])

    has_more_stamps = has_prev_stamps = False

    if stamps:
        next_id = stamps[-1].id
        prev_id = stamps[0].id

        has_more_stamps = query.filter(id__lt=next_id).exists()
        has_prev_stamps = query.filter(id__gt=prev_id).exists()

    stamps = [{"version": "1.0.0", "credential": stamp.credential} for stamp in stamps]

    domain = request.build_absolute_uri("/")[:-1]

    next_url = (
        f"""{domain}{reverse_lazy_with_query(
            "registry:get_passport_stamps",
            args=[address],
            query_kwargs={"token": encode_cursor("next", next_id), "limit": limit},
        )}"""
        if has_more_stamps
        else None
    )

    prev_url = (
        f"""{domain}{reverse_lazy_with_query(
            "registry:get_passport_stamps",
            args=[address],
            query_kwargs={"token": encode_cursor("prev", prev_id), "limit": limit},
        )}"""
        if has_prev_stamps
        else None
    )

    response = CursorPaginatedStampCredentialResponse(
        next=next_url, prev=prev_url, items=stamps
    )

    return response


@analytics_router.get("/score/", auth=ApiKey(), response=CursorPaginatedScoreResponse)
@permissions_required([ResearcherPermission])
def get_scores_analytics(
    request, token: str = None, limit: int = 1000
) -> CursorPaginatedScoreResponse:
    if limit > 1000:
        raise InvalidLimitException()

    query = Score.objects.order_by("id").select_related("passport")

    direction, id = decode_cursor(token) if token else (None, None)

    if direction == "next":
        scores = list(query.filter(id__gt=id)[:limit])
    elif direction == "prev":
        scores = list(query.filter(id__lt=id).order_by("-id")[:limit])
        scores.reverse()
    else:
        scores = list(query[:limit])

    has_more_scores = has_prev_scores = False

    if scores:
        next_id = scores[-1].id
        prev_id = scores[0].id

        has_more_scores = query.filter(id__gt=next_id).exists()
        has_prev_scores = query.filter(id__lt=prev_id).exists()

    domain = request.build_absolute_uri("/")[:-1]

    next_url = (
        f"""{domain}{reverse_lazy_with_query(
            "analytics:get_scores_analytics",
            query_kwargs={"token": encode_cursor("next", next_id), "limit": limit},
        )}"""
        if has_more_scores
        else None
    )

    prev_url = (
        f"""{domain}{reverse_lazy_with_query(
            "analytics:get_scores_analytics",
            query_kwargs={"token": encode_cursor("prev", prev_id), "limit": limit},
        )}"""
        if has_prev_scores
        else None
    )

    response = CursorPaginatedScoreResponse(next=next_url, prev=prev_url, items=scores)

    return response


@analytics_router.get(
    "/score/{int:scorer_id}", auth=ApiKey(), response=CursorPaginatedScoreResponse
)
@permissions_required([ResearcherPermission])
def get_scores_by_community_id_analytics(
    request,
    scorer_id: int,
    address: str = "",
    token: str = None,
    limit: int = 1000,
) -> CursorPaginatedScoreResponse:
    if limit > 1000:
        raise InvalidLimitException()

    user_community = api_get_object_or_404(Community, id=scorer_id)

    query = (
        Score.objects.order_by("id")
        .filter(passport__community__id=user_community.id)
        .select_related("passport")
    )

    if address:
        query = query.filter(passport__address=address.lower())

    direction, id = decode_cursor(token) if token else (None, None)

    if direction == "next":
        scores = list(query.filter(id__gt=id)[:limit])
    elif direction == "prev":
        scores = list(query.filter(id__lt=id).order_by("-id")[:limit])
        scores.reverse()
    else:
        scores = list(query[:limit])

    has_more_scores = has_prev_scores = False

    if scores:
        next_id = scores[-1].id
        prev_id = scores[0].id

        has_more_scores = query.filter(id__gt=next_id).exists()
        has_prev_scores = query.filter(id__lt=prev_id).exists()

    domain = request.build_absolute_uri("/")[:-1]

    next_url = (
        f"""{domain}{reverse_lazy_with_query(
            "analytics:get_scores_by_community_id_analytics",
            args=[scorer_id],
            query_kwargs={"token": encode_cursor("next", next_id), "limit": limit},
        )}"""
        if has_more_scores
        else None
    )

    prev_url = (
        f"""{domain}{reverse_lazy_with_query(
            "analytics:get_scores_by_community_id_analytics",
            args=[scorer_id],
            query_kwargs={"token": encode_cursor("prev", prev_id), "limit": limit},
        )}"""
        if has_prev_scores
        else None
    )

    response = CursorPaginatedScoreResponse(next=next_url, prev=prev_url, items=scores)

    return response
