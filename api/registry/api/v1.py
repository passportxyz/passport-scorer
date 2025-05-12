from decimal import Decimal
from typing import List
from urllib.parse import urljoin
from decimal import Decimal

import django_filters
import requests
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from ninja import Router
from ninja.pagination import paginate
from ninja_extra.exceptions import APIException

import api_logging as logging
from account.api import UnauthorizedException, create_community_for_account

# --- Deduplication Modules
from account.models import (
    Account,
    AccountAPIKey,
    Community,
    Nonce,
    Rules,
)
from ceramic_cache.models import CeramicCache
from registry.api.schema import (
    CursorPaginatedStampCredentialResponse,
    DetailedScoreResponse,
    ErrorMessageResponse,
    GenericCommunityPayload,
    GenericCommunityResponse,
    GtcEventsResponse,
    SigningMessageResponse,
    StampDisplayResponse,
    SubmitPassportPayload,
)
from registry.api.utils import (
    ApiKey,
    aapi_key,
    atrack_apikey_usage,
    check_rate_limit,
    community_requires_signature,
    get_scorer_id,
    is_valid_address,
    track_apikey_usage,
    with_read_db,
)
from registry.atasks import ascore_passport
from registry.exceptions import (
    InternalServerErrorException,
    InvalidAddressException,
    InvalidAPIKeyPermissions,
    InvalidCommunityScoreRequestException,
    InvalidLimitException,
    InvalidNonceException,
    InvalidOrderByFieldException,
    InvalidSignerException,
    NotFoundApiException,
    StakingRequestError,
    aapi_get_object_or_404,
    api_get_object_or_404,
)
from registry.filters import GTCStakeEventsFilter
from registry.models import GTCStakeEvent, Passport, Score
from registry.utils import (
    decode_cursor,
    encode_cursor,
    get_signer,
    get_signing_message,
    reverse_lazy_with_query,
)

User = get_user_model()


SCORE_TIMESTAMP_FIELD_DESCRIPTION = """
The optional `timestamp` query parameter can be used to retrieve
the latest score for an address as of that timestamp.
It is expected to be an ISO 8601 formatted timestamp.\n

Examples of valid values for `timestamp`: \n
- 2023-05-10T07:49:08Z\n
- 2023-05-10T07:49:08.610198+00:00\n
- 2023-05-10\n
"""


METADATA_URL = urljoin(settings.PASSPORT_PUBLIC_URL, "stampMetadata.json")

log = logging.getLogger(__name__)
# api = NinjaExtraAPI(urls_namespace="registry")
router = Router()


feature_flag_router = Router()


@router.get(
    "/signing-message",
    auth=ApiKey(),
    response={
        200: SigningMessageResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
    },
    summary="Retrieve a signing message",
    description="""Use this API to get a message to sign and a nonce to use when submitting your passport for scoring.""",
)
@track_apikey_usage(track_response=False)
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
# def submit_passport(request, payload: SubmitPassportPayload) -> DetailedScoreResponse:
#     check_rate_limit(request)

#     # Get DID from address
#     # did = get_did(payload.address)
#     log.debug("/submit-passport, payload=%s", payload)

#     account = request.auth

#     if not request.api_key.submit_passports:
#         raise InvalidAPIKeyPermissions()

#     return handle_submit_passport(payload, account)


@router.post(
    "/submit-passport",
    auth=aapi_key,
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Submit an Ethereum address to the Scorer",
    description="""Use this API to submit your passport for scoring.\n
This API will return a `DetailedScoreResponse` structure with status **PROCESSING** or **DONE**.\n
If the status is **DONE** the final score is provided in this response.\n
If the status is **PROCESSING**, this means that your passport is being pulled from storage and the scoring algorithm is run in the background. You need to check for the status of the operation by calling the `/score/{int:scorer_id}/{str:address}` API. The operation will have finished when the status returned is **DONE**
""",
)
@atrack_apikey_usage(track_response=True, payload_param_name="payload")
async def a_submit_passport(
    request, payload: SubmitPassportPayload
) -> DetailedScoreResponse:
    check_rate_limit(request)
    try:
        log.debug("called a_submit_passport, payload=%s", payload)

        if not request.api_key.submit_passports:
            raise InvalidAPIKeyPermissions()

        return await ahandle_submit_passport(payload, request.auth)
    except APIException as e:
        raise e
    except Exception as e:
        log.exception("Error submitting passport: %s", e)
        raise InternalServerErrorException(
            "Unexpected error while submitting passport"
        ) from e


async def ahandle_submit_passport(
    payload: SubmitPassportPayload, account: Account
) -> DetailedScoreResponse:
    address_lower = payload.address.lower()
    if not is_valid_address(address_lower):
        raise InvalidAddressException()

    try:
        scorer_id = get_scorer_id(payload)
    except Exception as e:
        raise e

    # Get community object
    user_community = await aget_scorer_by_id(scorer_id, account)

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
    # score, _ = await Score.objects.aupdate_or_create(
    #     passport_id=db_passport.pk,
    #     defaults=dict(score=None, status=Score.Status.PROCESSING),
    # )
    # score.passport = db_passport
    score, _ = await Score.objects.select_related("passport").aget_or_create(
        passport=db_passport,
        defaults=dict(score=None, status=Score.Status.PROCESSING),
    )

    await ascore_passport(user_community, db_passport, payload.address, score)
    await score.asave()

    scorer = await user_community.aget_scorer()
    if getattr(scorer, "type", None) == "WEIGHTED":
        return format_non_threshold_score(score)
    else:
        return DetailedScoreResponse.from_orm(score)


def handle_submit_passport(
    payload: SubmitPassportPayload, account: Account
) -> DetailedScoreResponse:
    return async_to_sync(ahandle_submit_passport)(payload, account)


def get_scorer_by_id(scorer_id: int | str, account: Account) -> Community:
    try:
        return with_read_db(Community).get(
            external_scorer_id=scorer_id, account=account
        )
    except Exception:
        return api_get_object_or_404(
            with_read_db(Community), id=scorer_id, account=account
        )


async def aget_scorer_by_id(scorer_id: int | str, account: Account) -> Community:
    try:
        ret = await with_read_db(Community).aget(
            external_scorer_id=scorer_id, account=account
        )
        return ret
    except Exception:
        try:
            ret = await aapi_get_object_or_404(
                with_read_db(Community), id=scorer_id, account=account
            )
            return ret
        except Exception as exc:
            log.error(
                "Error when getting score by internal or external ID (aget_scorer_by_id): scorer_id/external_scorer_id=%s, account='%s'",
                scorer_id,
                account,
                exc_info=True,
            )
            raise NotFoundApiException("No scorer matches the given criteria.") from exc


@router.get(
    "/score/{int:scorer_id}/{str:address}",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Retrieve a Passport score for one address",
    description=f"""Use this endpoint to fetch the score for a specific address that is associated with a scorer\n
This endpoint will return a `DetailedScoreResponse`. This endpoint will also return the status of the asynchronous operation that was initiated with a request to the `/submit-passport` API.\n
{SCORE_TIMESTAMP_FIELD_DESCRIPTION}
""",
)
@track_apikey_usage(track_response=False)
def get_score(request, address: str, scorer_id: int | str) -> DetailedScoreResponse:
    check_rate_limit(request)
    account = request.auth

    if not request.api_key.read_scores:
        raise InvalidAPIKeyPermissions()

    return handle_get_score(address, scorer_id, account)


def format_non_threshold_score(score: Score) -> DetailedScoreResponse:
    # For backward compatibility, use the raw score as the Score model's .score field
    raw_score = None
    if score.evidence and "rawScore" in score.evidence:
        try:
            raw_score = Decimal(score.evidence["rawScore"])
        except Exception:
            raw_score = score.evidence["rawScore"]
    if raw_score is None:
        raw_score = score.score
    # Patch the score object for compatibility
    score.score = raw_score
    return DetailedScoreResponse(
        address=score.passport.address,
        score=raw_score,
        status=score.status,
        last_score_timestamp=score.last_score_timestamp,
        expiration_date=score.expiration_date,
        evidence=None,
        error=score.error,
        stamp_scores=score.stamp_scores or {},
    )


def format_non_threshold_score(score: Score) -> DetailedScoreResponse:
    # For backward compatibility, use the raw score as the Score model's .score field
    raw_score = None
    if score.evidence and "rawScore" in score.evidence:
        try:
            raw_score = Decimal(score.evidence["rawScore"])
        except Exception:
            raw_score = score.evidence["rawScore"]
    if raw_score is None:
        raw_score = score.score
    # Patch the score object for compatibility
    score.score = raw_score
    return DetailedScoreResponse(
        address=score.passport.address,
        score=raw_score,
        status=score.status,
        last_score_timestamp=score.last_score_timestamp,
        expiration_date=score.expiration_date,
        evidence=None,
        error=score.error,
        stamp_scores=score.stamp_scores or {},
    )


def handle_get_score(
    address: str, scorer_id: int, account: Account
) -> DetailedScoreResponse:
    # Get community object
    user_community = get_scorer_by_id(scorer_id, account)

    try:
        lower_address = address.lower()

        if not is_valid_address(lower_address):
            raise InvalidAddressException()

        score = Score.objects.get(
            passport__address=lower_address, passport__community=user_community
        )

        scorer = user_community.get_scorer()

        if getattr(scorer, "type", None) == "WEIGHTED":
            return format_non_threshold_score(score)
        else:
            return DetailedScoreResponse.from_orm(score)

    except NotFoundApiException as e:
        raise e
    except Exception as e:
        log.error(
            "Error getting passport scores. scorer_id=%s",
            scorer_id,
            exc_info=True,
        )
        raise InvalidCommunityScoreRequestException() from e


class ScoreFilter(django_filters.FilterSet):
    last_score_timestamp__gt = django_filters.IsoDateTimeFilter(
        field_name="last_score_timestamp", lookup_expr="gt"
    )
    last_score_timestamp__gte = django_filters.IsoDateTimeFilter(
        field_name="last_score_timestamp", lookup_expr="gte"
    )
    address = django_filters.CharFilter(
        field_name="passport__address", lookup_expr="iexact"
    )

    class Meta:
        model = Score
        fields = ["last_score_timestamp"]


@router.get(
    "/score/{int:scorer_id}",
    auth=ApiKey(),
    response={
        200: List[DetailedScoreResponse],
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Retrieve the Passport scores for all submitted addresses",
    description="""Use this endpoint to fetch the scores for all addresses that are associated with a scorer\n
This API will return a list of `DetailedScoreResponse` objects. The endpoint supports pagination and will return a maximum of 1000 scores per request.\n
Pass a limit and offset query parameter to paginate the results. For example: `/score/1?limit=100&offset=100` will return the second page of 100 scores.\n
The `last_score_timestamp__gt` and `last_score_timestamp__gte` query parameters are expected to be ISO 8601 formatted timestamps:\n
- `last_score_timestamp__gt` - will return only results having the timestamp greater than the provided value.\n
- `last_score_timestamp__gte` - will return only results having the timestamp greater or equal than the provided value.\n

Examples of valid values for `last_score_timestamp__gt` and `last_score_timestamp__gt` filters: \n
- 2023-05-10T07:49:08Z\n
- 2023-05-10T07:49:08.610198+00:00\n
- 2023-05-10\n

Please note that while using both parameters (`last_score_timestamp__gt` and `last_score_timestamp__gte`) is possible and both filters are applied. \
But this generally makes no sense.
""",
)
@paginate(pass_parameter="pagination_info")
@track_apikey_usage(track_response=False)
def get_scores(
    request,
    scorer_id: int,
    address: str = "",
    last_score_timestamp__gt: str = "",
    last_score_timestamp__gte: str = "",
    order_by: str = "id",
    **kwargs,
) -> List[DetailedScoreResponse]:
    check_rate_limit(request)
    if kwargs["pagination_info"].limit > 1000:
        raise InvalidLimitException()

    if not request.api_key.read_scores:
        raise InvalidAPIKeyPermissions()

    # Get community object
    user_community = get_scorer_by_id(scorer_id, request.auth)

    try:
        ORDER_BY_MAPPINGS = {
            "last_score_timestamp": "last_score_timestamp",
            "id": "pk",
        }

        ordered_by = ORDER_BY_MAPPINGS.get(order_by)

        if not ordered_by:
            raise InvalidOrderByFieldException()

        scores = (
            with_read_db(Score)
            .filter(passport__community__id=user_community.pk)
            .order_by(ordered_by)
            .select_related("passport")
        )

        filter_values = {
            "address": address,
            "last_score_timestamp__gt": last_score_timestamp__gt,
            "last_score_timestamp__gte": last_score_timestamp__gte,
        }
        # Technically we could just pass request.GET to the filter. But since we have the parameters defined
        # anyways (because we need them for the generated docs) we might as well use them explicitly in the
        # filter_values.
        scores = ScoreFilter(filter_values, queryset=scores).qs

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
    summary="Receive Stamps verified by submitted Passports",
    description="""Use this endpoint to fetch the passport for a specific address\n
This endpoint will return a `CursorPaginatedStampCredentialResponse`.\n
**WARNING**: The **include_metadata** feature is in beta, the metadata response format may change in the future.\n
""",
    # This prevents returning {metadata: None} in the response
    exclude_unset=True,
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
        except Exception:
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
    except Exception:
        log.exception("Error fetching external metadata")
        raise InternalServerErrorException(
            "Error fetching external stamp metadata for provider " + provider
        )

    return metadataByProvider.get(provider)


@router.get(
    "/stamp-metadata",
    summary="Receive all Stamps available in Passport",
    description="""**WARNING**: This endpoint is in beta and is subject to change.""",
    auth=ApiKey(),
    response={
        200: List[StampDisplayResponse],
        500: ErrorMessageResponse,
    },
)
@track_apikey_usage(track_response=False)
def stamp_display(request) -> List[StampDisplayResponse]:
    check_rate_limit(request)
    return fetch_all_stamp_metadata()


@router.get(
    "/gtc-stake/{str:address}/{int:round_id}",
    # auth=ApiKey(),
    auth=None,
    response=GtcEventsResponse,
    summary="Deprecated: Retrieve GTC stake amounts from legacy staking contract",
    description="Get self and community GTC staking amounts based on address and round ID",
    deprecated=True,
)
def get_gtc_stake_legacy(request, address: str, round_id: int) -> GtcEventsResponse:
    return handle_get_gtc_stake_legacy(address, round_id)


def handle_get_gtc_stake_legacy(address: str, round_id: int) -> GtcEventsResponse:
    """
    Get GTC stake amount by address and round ID (from legacy contract)
    """
    address = address.lower()

    if not is_valid_address(address):
        raise InvalidAddressException()

    params = {"address": address, "round_id": round_id}

    try:
        queryset = with_read_db(GTCStakeEvent)
        filtered_queryset = GTCStakeEventsFilter(data=params, queryset=queryset).qs
        return {"results": [obj for obj in filtered_queryset.values()]}
    except Exception:
        raise StakingRequestError()
