from datetime import datetime
from typing import Dict, List
from urllib.parse import urljoin

import api_logging as logging
import requests
from account.api import UnauthorizedException, create_community_for_account
from account.deduplication.fifo import afifo
from account.deduplication.lifo import alifo

# --- Deduplication Modules
from account.models import Account, Community, Nonce, Rules
from ceramic_cache.models import CeramicCache
from django.conf import settings
from django.core.cache import cache
from ninja import Router
from ninja.pagination import paginate
from ninja_extra.exceptions import APIException
from reader.passport_reader import get_did
from registry.exceptions import NoPassportException
from registry.models import Passport, Score, Stamp
from registry.permissions import ResearcherPermission
from registry.utils import (
    decode_cursor,
    encode_cursor,
    get_signer,
    get_signing_message,
    permissions_required,
    reverse_lazy_with_query,
    validate_credential,
    verify_issuer,
)

from ..exceptions import (
    InternalServerErrorException,
    InvalidAPIKeyPermissions,
    InvalidCommunityScoreRequestException,
    InvalidLimitException,
    InvalidNonceException,
    InvalidSignerException,
    aapi_get_object_or_404,
    api_get_object_or_404,
)
from ..tasks import get_utc_time, score_passport_passport, score_registry_passport
from .base import (
    ApiKey,
    aapi_key,
    check_rate_limit,
    community_requires_signature,
    get_scorer_id,
)
from .schema import (
    CursorPaginatedScoreResponse,
    CursorPaginatedStampCredentialResponse,
    DetailedScoreResponse,
    ErrorMessageResponse,
    GenericCommunityPayload,
    GenericCommunityResponse,
    SigningMessageResponse,
    StampDisplayResponse,
    SubmitPassportPayload,
)

METADATA_URL = urljoin(settings.PASSPORT_PUBLIC_URL, "stampMetadata.json")

log = logging.getLogger(__name__)
# api = NinjaExtraAPI(urls_namespace="registry")
router = Router()

analytics_router = Router()

feature_flag_router = Router()


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


# @router.post(
#     "/submit-passport",
#     auth=ApiKey(),
#     response={
#         200: DetailedScoreResponse,
#         401: ErrorMessageResponse,
#         400: ErrorMessageResponse,
#         404: ErrorMessageResponse,
#     },
#     summary="Submit passport for scoring",
#     description="""Use this API to submit your passport for scoring.\n
# This API will return a `DetailedScoreResponse` structure with status **PROCESSING** immediatly while your passport is being pulled from storage and the scoring algorithm is run.\n
# You need to check for the status of the operation by calling the `/score/{int:scorer_id}/{str:address}` API. The operation will have finished when the status returned is **DONE**
# """,
# )
def submit_passport(request, payload: SubmitPassportPayload) -> DetailedScoreResponse:
    check_rate_limit(request)

    # Get DID from address
    # did = get_did(payload.address)
    log.debug("/submit-passport, payload=%s", payload)

    account = request.auth

    if not request.api_key.submit_passports:
        raise InvalidAPIKeyPermissions()

    return handle_submit_passport(payload, account)


@router.post(
    "/submit-passport",
    auth=aapi_key,
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
    # Don't list in the docs for now
    include_in_schema=False,
)
async def a_submit_passport(
    request, payload: SubmitPassportPayload
) -> DetailedScoreResponse:
    check_rate_limit(request)

    # Get DID from address
    # did = get_did(payload.address)
    log.error("/submit-passport, payload=%s", payload)

    account = request.auth

    if not request.api_key.submit_passports:
        raise InvalidAPIKeyPermissions()

    return await ahandle_submit_passport(payload, account)


async def aremove_existing_stamps_from_db(passport: Passport):
    await Stamp.objects.filter(passport=passport).adelete()


async def aget_passport(address: str = "", stream_ids: List[str] = []) -> Dict:
    did = get_did(address)

    db_stamp_list = CeramicCache.objects.filter(address=address)

    # TODO: add back loading from ceramic
    # if len(db_stamp_list) == 0:
    #     # get streamIds if non are provided
    #     stream_ids = (
    #         stream_ids
    #         if len(stream_ids) > 0
    #         else get_stream_ids(did, [CERAMIC_GITCOIN_PASSPORT_STREAM_ID])
    #     )

    #     # attempt to pull content
    #     passport = get_stamps(get_passport_stream(stream_ids))

    #     # return a list of wallet address without the @eip155:1 suffix
    #     return passport
    # else:
    return {
        "stamps": [
            {"provider": s.provider, "credential": s.stamp} async for s in db_stamp_list
        ]
    }


async def aload_passport_data(address: str) -> Dict:
    # Get the passport data from the blockchain or ceramic cache
    passport_data = await aget_passport(address)
    if not passport_data:
        raise NoPassportException()

    log.error("=" * 40)
    log.error("=" * 40)
    from pprint import pformat

    log.error("%s", pformat(passport_data))
    log.error("=" * 40)
    log.error("=" * 40)
    return passport_data


async def acalculate_score(passport: Passport, community_id: int):
    log.debug("Scoring")
    user_community = await Community.objects.aget(pk=community_id)

    scorer = await user_community.aget_scorer()
    scores = await scorer.acompute_score([passport.pk])

    log.info("Scores for address '%s': %s", passport.address, scores)
    scoreData = scores[0]

    await Score.objects.aupdate_or_create(
        passport_id=passport.pk,
        defaults=dict(
            score=scoreData.score,
            status=Score.Status.DONE,
            last_score_timestamp=get_utc_time(),
            evidence=scoreData.evidence[0].as_dict() if scoreData.evidence else None,
            error=None,
        ),
    )


async def aprocess_deduplication(passport, community, passport_data):
    """
    Process deduplication based on the community rule
    """
    rule_map = {
        Rules.LIFO.value: alifo,
        Rules.FIFO.value: afifo,
    }

    method = rule_map.get(community.rule)

    log.debug(
        "Processing deduplication for address='%s' and method='%s'",
        passport.address,
        method,
    )

    if not method:
        raise Exception("Invalid rule")

    deduplicated_passport, affected_passports = await method(
        community, passport_data, passport.address
    )

    log.debug(
        "Processing deduplication found deduplicated_passport='%s' and affected_passports='%s'",
        deduplicated_passport,
        affected_passports,
    )

    # If the rule is FIFO, we need to re-score all affected passports
    if community.rule == Rules.FIFO.value:
        for passport in affected_passports:
            log.debug(
                "FIFO scoring selected, rescoring passport='%s'",
                passport,
            )

            await Score.objects.aupdate_or_create(
                passport=passport,
                defaults=dict(score=None, status=Score.Status.PROCESSING),
            )
            await acalculate_score(passport, passport.community_id)

    return deduplicated_passport


async def avalidate_and_save_stamps(
    passport: Passport, community: Community, passport_data
):
    log.debug("getting stamp data ")

    log.debug("processing deduplication")

    deduped_passport_data = await aprocess_deduplication(
        passport, community, passport_data
    )

    log.debug("validating stamps")
    did = get_did(passport.address)

    for stamp in deduped_passport_data["stamps"]:
        stamp_return_errors = await validate_credential(did, stamp["credential"])
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
            await Stamp.objects.aupdate_or_create(
                hash=stamp["credential"]["credentialSubject"]["hash"],
                passport=passport,
                defaults={
                    "provider": stamp["provider"],
                    "credential": stamp["credential"],
                },
            )
        else:
            log.info(
                "Stamp not created. Stamp=%s\nReason: errors=%s stamp_is_expired=%s is_issuer_verified=%s",
                stamp,
                stamp_return_errors,
                stamp_is_expired,
                is_issuer_verified,
            )


async def ascore_passport(community: Community, passport: Passport, address: str):
    log.info(
        "score_passport request for community_id=%s, address='%s'",
        community.id,
        address,
    )

    try:
        # passport = load_passport_record(community_id, address)
        log.error("===> 1")
        await aremove_existing_stamps_from_db(passport)
        log.error("===> 2")
        passport_data = await aload_passport_data(address)
        log.error("===> 3")
        await avalidate_and_save_stamps(passport, community, passport_data)
        log.error("===> 4")
        await acalculate_score(passport, community.id)
        log.error("===> 5")

    except APIException as e:
        log.error(
            "APIException when handling passport submission. community_id=%s, address='%s'",
            community.id,
            address,
            exc_info=True,
        )
        if passport:
            # Create a score with error status
            await Score.objects.aupdate_or_create(
                passport_id=passport.pk,
                defaults=dict(
                    score=None,
                    status=Score.Status.ERROR,
                    last_score_timestamp=None,
                    evidence=None,
                    error=e.detail,
                ),
            )
    except Exception as e:
        log.error(
            "Error when handling passport submission. community_id=%s, address='%s'",
            community.id,
            address,
            exc_info=True,
        )
        if passport:
            # Create a score with error status
            await Score.objects.aupdate_or_create(
                passport_id=passport.pk,
                defaults=dict(
                    score=None,
                    status=Score.Status.ERROR,
                    last_score_timestamp=None,
                    evidence=None,
                    error=str(e),
                ),
            )


async def ahandle_submit_passport(
    payload: SubmitPassportPayload, account: Account
) -> DetailedScoreResponse:
    address_lower = payload.address.lower()

    try:
        scorer_id = get_scorer_id(payload)
        log.error("===> scorer_id %s", scorer_id)
    except Exception as e:
        raise e

    # Get community object
    user_community = await aget_scorer_by_id(scorer_id, account)
    log.error("===> user_community %s", user_community)

    # Verify the signer
    if payload.signature or community_requires_signature(user_community):
        if get_signer(payload.nonce, payload.signature).lower() != address_lower:
            raise InvalidSignerException()

        # Verify nonce
        if not await Nonce.ause_nonce(payload.nonce):
            log.error("Invalid nonce %s for address %s", payload.nonce, payload.address)
            raise InvalidNonceException()

    # Create an empty passport instance, only needed to be able to create a pending Score
    # The passport will be updated by the score_passport task
    db_passport, _ = await Passport.objects.aupdate_or_create(
        address=payload.address.lower(),
        community=user_community,
    )

    # Create a score with status PROCESSING
    score, _ = await Score.objects.aupdate_or_create(
        passport_id=db_passport.pk,
        defaults=dict(score=None, status=Score.Status.PROCESSING),
    )

    await ascore_passport(user_community, db_passport, payload.address)

    passport = await Passport.objects.aget(pk=score.passport_id)

    score = await Score.objects.aget(id=score.id)
    return DetailedScoreResponse(
        address=passport.address,
        score=score.score,
        status=score.status,
        evidence=score.evidence,
        last_score_timestamp=score.last_score_timestamp.isoformat()
        if score.last_score_timestamp
        else None,
    )


def handle_submit_passport(
    payload: SubmitPassportPayload, account: Account, use_passport_task: bool = False
) -> DetailedScoreResponse:
    address_lower = payload.address.lower()

    try:
        scorer_id = get_scorer_id(payload)
    except Exception as e:
        raise e

    # Get community object
    user_community = get_scorer_by_id(scorer_id, account)

    # Verify the signer
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
            "requires_calculation": True,
        },
    )

    # Create a score with status PROCESSING
    score, _ = Score.objects.update_or_create(
        passport_id=db_passport.pk,
        defaults=dict(score=None, status=Score.Status.PROCESSING),
    )

    if use_passport_task:
        score_passport_passport.delay(user_community.pk, payload.address)
    else:
        score_registry_passport.delay(user_community.pk, payload.address)

    return DetailedScoreResponse(
        address=score.passport.address,
        score=score.score,
        status=score.status,
        evidence=score.evidence,
        last_score_timestamp=score.last_score_timestamp.isoformat()
        if score.last_score_timestamp
        else None,
    )


def get_scorer_by_id(scorer_id: int | str, account: Account) -> Community:
    try:
        return Community.objects.get(external_scorer_id=scorer_id, account=account)
    except Exception:
        return api_get_object_or_404(Community, id=scorer_id, account=account)


async def aget_scorer_by_id(scorer_id: int | str, account: Account) -> Community:
    try:
        ret = await Community.objects.aget(
            external_scorer_id=scorer_id, account=account
        )
        log.error("===> aget_scorer_by_id %s", ret)
        return ret
    except Exception:
        ret = await aapi_get_object_or_404(Community, id=scorer_id, account=account)
        log.error("===> exc aget_scorer_by_id %s", aget_scorer_by_id)
        return ret


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
def get_score(request, address: str, scorer_id: int | str) -> DetailedScoreResponse:
    check_rate_limit(request)
    account = request.auth

    if not request.api_key.read_scores:
        raise InvalidAPIKeyPermissions()

    return handle_get_score(address, scorer_id, account)


def handle_get_score(
    address: str, scorer_id: int, account: Account
) -> DetailedScoreResponse:
    # Get community object
    user_community = get_scorer_by_id(scorer_id, account)

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

    if not request.api_key.read_scores:
        raise InvalidAPIKeyPermissions()

    # Get community object
    user_community = get_scorer_by_id(scorer_id, request.auth)

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
**WARNING**: The **include_metadata** feature is in beta, the metadata response format may change in the future.\n
""",
    # This prevents returning {metadata: None} in the response
    exclude_unset=True,
)
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

    query = CeramicCache.objects.order_by("-id").filter(address=address.lower())

    direction, id = decode_cursor(token) if token else (None, None)

    if direction == "next":
        # note we use lt here because we're querying in descending order
        cacheStamps = list(query.filter(id__lt=id)[:limit])

    elif direction == "prev":
        cacheStamps = list(query.filter(id__gt=id).order_by("id")[:limit])
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


@feature_flag_router.post(
    "/scorer/generic",
    auth=ApiKey(),
    response={
        200: GenericCommunityResponse,
        400: ErrorMessageResponse,
        401: ErrorMessageResponse,
    },
    summary="Programmatically create a generic scorer",
    description="""This endpoint allows the creation of new scorers.\n
You must have the correct permissions to make requests to this endpoint.\n
Anyone can go to https://www.scorer.gitcoin.co/ and create a new scorer via the UI.\n
""",
)
def create_generic_scorer(request, payload: GenericCommunityPayload):
    try:
        account = request.auth
        if not request.api_key.create_scorers:
            raise InvalidAPIKeyPermissions()

        community = create_community_for_account(
            account,
            payload.name,
            payload.description,
            settings.GENERIC_COMMUNITY_CREATION_LIMIT,
            use_case="Sybil Protection",
            rule=Rules.LIFO.value,
            scorer="WEIGHTED",
            external_scorer_id=payload.external_scorer_id,
        )

        return {
            "ok": True,
            "scorer_id": community.pk,
            "external_scorer_id": community.external_scorer_id,
        }

    except Account.DoesNotExist:
        raise UnauthorizedException()


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

    next_id = prev_id = 0
    has_more_scores = has_prev_scores = False
    if scores:
        next_id = scores[-1].pk
        prev_id = scores[0].pk

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

    next_id = prev_id = 0
    has_more_scores = has_prev_scores = False
    if scores:
        next_id = scores[-1].pk
        prev_id = scores[0].pk

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


def fetch_all_stamp_metadata() -> List[StampDisplayResponse]:
    # Try to get the metadata from the cache
    metadata = cache.get("metadata")

    # If it's not in the cache, fetch it from the external API
    if metadata is None:
        try:
            response = requests.get(METADATA_URL)
            response.raise_for_status()

            responseJson = response.json()

            # Append base URL to icon URLs
            metadata = [
                StampDisplayResponse(
                    **{
                        **platformData,
                        "icon": urljoin(
                            settings.PASSPORT_PUBLIC_URL, platformData["icon"]
                        ),
                    }
                )
                for platformData in responseJson
            ]

            # Store the metadata in the cache, with a timeout of 1 hour
            cache.set("metadata", metadata, 60 * 60)
        except:
            log.exception("Error fetching external metadata")

    if metadata is None:
        raise InternalServerErrorException("Error fetching external stamp metadata")

    return metadata


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
    except:
        log.exception("Error fetching external metadata")
        raise InternalServerErrorException(
            "Error fetching external stamp metadata for provider " + provider
        )

    return metadataByProvider.get(provider)


@router.get(
    "/stamp-metadata",
    description="""**WARNING**: This endpoint is in beta and is subject to change.""",
    auth=ApiKey(),
    response={
        200: List[StampDisplayResponse],
        500: ErrorMessageResponse,
    },
)
def stamp_display(request) -> List[StampDisplayResponse]:
    check_rate_limit(request)
    return fetch_all_stamp_metadata()
