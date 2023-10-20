"""Ceramic Cache API"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type

import api_logging as logging
import requests
from account.models import Account, Nonce
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja_extra import status
from ninja_extra.exceptions import APIException
from ninja_extra.security import HttpBearer
from ninja_jwt.authentication import InvalidToken

# from ninja_jwt.schema import RefreshToken
from ninja_jwt.settings import api_settings
from ninja_jwt.tokens import RefreshToken, Token, TokenError
from ninja_schema import Schema
from registry.api.v1 import (
    DetailedScoreResponse,
    SubmitPassportPayload,
    ahandle_submit_passport,
    handle_get_score,
    handle_submit_passport,
)
from registry.models import Score

from ..exceptions import (
    InternalServerException,
    InvalidDeleteCacheRequestException,
    TooManyStampsException,
)
from ..models import CeramicCache
from ..utils import validate_dag_jws_payload, verify_jws

log = logging.getLogger(__name__)

router = Router()


def get_utc_time():
    return datetime.utcnow()


def get_address_from_did(did: str):
    return did.split(":")[-1]


class JWTDidAuthentication:
    """
    This authentication class will validate an access token that contains a claim named `did`
    and will save that value in `request.did`
    """

    def __init__(self) -> None:
        super().__init__()
        self.user_model = get_user_model()

    @classmethod
    def get_validated_token(cls, raw_token) -> Type[Token]:
        """
        Validates an encoded JSON web token and returns a validated token
        wrapper object.
        """
        messages = []
        for AuthToken in api_settings.AUTH_TOKEN_CLASSES:
            try:
                ret = AuthToken(raw_token)
                return ret
            except TokenError as e:
                messages.append(
                    {
                        "token_class": AuthToken.__name__,
                        "token_type": AuthToken.token_type,
                        "message": e.args[0],
                    }
                )

        raise InvalidToken(
            {
                "detail": "Given token not valid for any token type",
                "messages": messages,
            }
        )

    def jwt_authenticate(self, request: HttpRequest, token: str) -> Type[AbstractUser]:
        request.did = None
        validated_token = self.get_validated_token(token)
        request.did = validated_token["did"]
        return request


class JWTDidAuth(JWTDidAuthentication, HttpBearer):
    """
    This authentication class to check for did claim in the token
    """

    def authenticate(self, request: HttpRequest, token: str) -> Any:
        return self.jwt_authenticate(request, token)


class CacheStampPayload(Schema):
    address: Optional[str]
    provider: str
    stamp: Any


class DeleteStampPayload(Schema):
    address: Optional[str]
    provider: str


class CachedStampResponse(Schema):
    address: str
    provider: str
    stamp: Any


class GetStampResponse(Schema):
    success: bool
    stamps: List[CachedStampResponse]


class GetStampsWithScoreResponse(GetStampResponse):
    score: DetailedScoreResponse


@router.post(
    "stamps/bulk", response={201: GetStampsWithScoreResponse}, auth=JWTDidAuth()
)
def cache_stamps(request, payload: List[CacheStampPayload]):
    try:
        address = get_address_from_did(request.did)

        return handle_add_stamps(address, payload)

    except Exception as e:
        raise e


def handle_add_stamps(
    address, payload: List[CacheStampPayload]
) -> GetStampsWithScoreResponse:
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    stamp_objects = []
    now = get_utc_time()
    for p in payload:
        stamp_object = CeramicCache(
            type=CeramicCache.StampType.V1,
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

    updated_passport_state = CeramicCache.objects.filter(
        address=address, type=CeramicCache.StampType.V1
    )

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


@router.patch(
    "stamps/bulk", response={200: GetStampsWithScoreResponse}, auth=JWTDidAuth()
)
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


def handle_patch_stamps(
    address: str, payload: List[CacheStampPayload]
) -> GetStampsWithScoreResponse:
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    stamp_objects = []
    providers_to_delete = []
    updated = []
    now = get_utc_time()

    for p in payload:
        if p.stamp:
            stamp_object = CeramicCache(
                type=CeramicCache.StampType.V1,
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
            # No need to filter by type on delete ... we delete everything V1 ans V2 alike
            address=address,
            provider__in=providers_to_delete,
        )
        stamps.delete()

    updated_passport_state = CeramicCache.objects.filter(
        address=address, type=CeramicCache.StampType.V1
    )

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


def handle_delete_stamps(
    address: str, payload: List[DeleteStampPayload]
) -> GetStampsWithScoreResponse:
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    stamps = CeramicCache.objects.filter(
        # We do not filter by type. The thinking is: if a user wants to delete a V2 stamp, then he wants to delete both the V1 and V2 stamps ...
        address=address,
        provider__in=[p.provider for p in payload],
    )
    if not stamps:
        raise InvalidDeleteCacheRequestException()
    stamps.delete()

    updated_passport_state = CeramicCache.objects.filter(address=address)

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


def handle_get_scorer_weights() -> Dict[str, str]:
    return settings.GITCOIN_PASSPORT_WEIGHTS


@router.get("stamp", response=GetStampResponse)
def get_stamps(request, address):
    try:
        return handle_get_stamps(address)
    except Exception as e:
        raise e


def handle_get_stamps(address):
    stamps = CeramicCache.objects.filter(
        address=address, type=CeramicCache.StampType.V1
    )

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
    return handle_get_ui_score(address)


def handle_get_ui_score(address: str) -> DetailedScoreResponse:
    scorer_id = settings.CERAMIC_CACHE_SCORER_ID
    account = get_object_or_404(Account, community__id=scorer_id)
    return handle_get_score(address, scorer_id, account)


@router.post(
    "/score/{str:address}",
    response=DetailedScoreResponse,
    auth=JWTDidAuth(),
)
def calc_score(request, address: str) -> DetailedScoreResponse:
    return get_detailed_score_response_for_address(address)


class CacaoVerifySubmit(Schema):
    issuer: str
    signatures: List[Dict]
    payload: str
    nonce: str
    cid: List[int]
    cacao: List[int]


class FailedVerificationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to authorize request"


class DbCacheToken(RefreshToken):
    # Lifetime of the token is set to 7 days (because this is the setting of the CACAO session)
    # But it should ideally be read out of the cacao
    lifetime: timedelta = timedelta(days=7)


class AccessTokenResponse(Schema):
    access: str


@router.post(
    "authenticate",
    response=AccessTokenResponse,
)
def authenticate(request, payload: CacaoVerifySubmit):
    """
    This method will validate a jws created with DagJWS, will validate by forwarding this to our validator
    it and return a JWT token.
    """
    return handle_authenticate(payload)


def handle_authenticate(payload: CacaoVerifySubmit) -> AccessTokenResponse:
    # First validate the payload
    # This will ensure that the payload signature was made for our unique nonce
    try:
        if not Nonce.use_nonce(payload.nonce):
            log.error("Invalid or expired nonce: '%s'", payload.nonce)
            raise FailedVerificationException(detail="Invalid nonce!")

        if not validate_dag_jws_payload({"nonce": payload.nonce}, payload.payload):
            log.error("Failed to validate nonce: '%s'", payload.nonce)
            raise FailedVerificationException(detail="Invalid nonce or payload!")

    except Exception as exc:
        log.error("Failed authenticate request: '%s'", payload.dict(), exc_info=True)
        raise FailedVerificationException(detail="Invalid nonce or payload!") from exc

    try:
        try:
            verify_jws(payload.dict())

        except Exception as exc:
            log.error(
                "Failed to authenticate request (verify_jws failed): '%s'",
                payload.dict(),
                exc_info=True,
            )
            raise FailedVerificationException(
                detail=f"Failed to authenticate request: {str(exc)}"
            ) from exc

        token = DbCacheToken()
        token["did"] = payload.issuer

        return {
            "access": str(token.access_token),
        }

        # r = requests.post(
        #     settings.CERAMIC_CACHE_CACAO_VALIDATION_URL, json=payload.dict(), timeout=30
        # )
        # if r.status_code == 200:
        #     token = DbCacheToken()
        #     token["did"] = payload.issuer

        #     return {
        #         "access": str(token.access_token),
        #     }

        # log.error(
        #     "Failed to validate did signature for: %s.\n%s\n%s",
        #     payload.dict(),
        #     r,
        #     r.text,
        # )
        # raise FailedVerificationException(detail=f"Verifier response: {str(r)}")

    except APIException:
        # re-raise API exceptions
        raise
    except Exception as esc:
        log.error(
            "Failed authenticate request (verify_jws failed): '%s'",
            payload.dict(),
            exc_info=True,
        )
        raise APIException(detail=f"Failed authenticate request: {str(esc)}") from esc


def get_detailed_score_response_for_address(address: str) -> DetailedScoreResponse:
    scorer_id = settings.CERAMIC_CACHE_SCORER_ID
    if not scorer_id:
        raise InternalServerException("Scorer ID not set")

    account = get_object_or_404(Account, community__id=scorer_id)

    submit_passport_payload = SubmitPassportPayload(
        address=address,
        scorer_id=scorer_id,
    )

    score = async_to_sync(ahandle_submit_passport)(submit_passport_payload, account)

    return DetailedScoreResponse.from_orm(score)


def submit_passport_from_cache(address: str) -> Optional[DetailedScoreResponse]:
    try:
        scorer_id = settings.CERAMIC_CACHE_SCORER_ID
        if not scorer_id:
            return None

        account = get_object_or_404(Account, community__id=scorer_id)

        payload = SubmitPassportPayload(
            address=address,
            scorer_id=scorer_id,
        )

        return handle_submit_passport(payload, account, True)
    except Exception:
        log.error(
            "Error when calling submit_passport_from_cache for address: '%s'",
            address,
            exc_info=True,
        )
