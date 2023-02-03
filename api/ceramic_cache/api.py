"""Ceramic Cache API"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Type

import requests
from django.conf import settings
from ninja import Router, Schema
from ninja_extra import status
from ninja_extra.exceptions import APIException
from ninja_jwt.tokens import RefreshToken

from .exceptions import InvalidDeleteCacheRequestException
from .models import CeramicCache

from django.conf import settings
from django.contrib.auth import get_user_model
from ninja import Schema
from ninja_extra import status
from ninja_extra.exceptions import APIException
from ninja_jwt.schema import RefreshToken
from ninja_schema import Schema
from ninja_jwt.tokens import Token, TokenError
from ninja_jwt.authentication import InvalidToken
from django.contrib.auth.models import AbstractUser
from ninja_extra.security import HttpBearer
from django.http import HttpRequest
from ninja_jwt.settings import api_settings

log = logging.getLogger(__name__)

router = Router()


def get_utc_time():
    return datetime.utcnow()


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
                "detail": _("Given token not valid for any token type"),
                "messages": messages,
            }
        )

    def jwt_authenticate(self, request: HttpRequest, token: str) -> Type[AbstractUser]:
        request.did = None
        validated_token = self.get_validated_token(token)
        request.did = validated_token["did"]
        return request.did


class JWTDidAuth(JWTDidAuthentication, HttpBearer):
    """
    This authentication class to check for did claim in the token
    """

    def authenticate(self, request: HttpRequest, token: str) -> Any:
        return self.jwt_authenticate(request, token)


class CacheStampPayload(Schema):
    address: str
    provider: str
    stamp: Any


class DeleteStampPayload(Schema):
    address: str
    provider: str


class DeleteStampResponse(Schema):
    address: str
    provider: str
    status: str


class CachedStampResponse(Schema):
    address: str
    provider: str
    stamp: Any


class GetStampResponse(Schema):
    success: bool
    stamps: List[CachedStampResponse]


@router.post(
    "stamp",
    response={201: CachedStampResponse},
    # auth=JWTDidAuth()    <-- to be uncommented in order to enable authentication
)
def cache_stamp(_, payload: CacheStampPayload):
    try:
        stamp, created = CeramicCache.objects.update_or_create(
            address=payload.address,
            provider=payload.provider,
            defaults=dict(
                stamp=payload.stamp,
                deleted_at=None,
            ),
        )
        return stamp
    except Exception as e:
        raise e


@router.delete(
    "stamp",
    response=DeleteStampResponse,
    # auth=JWTDidAuth()    <-- to be uncommented in order to enable authentication
)
def soft_delete_stamp(_, payload: DeleteStampPayload):
    try:
        stamp = CeramicCache.objects.get(
            address=payload.address,
            provider=payload.provider,
        )
        stamp.deleted_at = get_utc_time()
        stamp.save()

        return DeleteStampResponse(
            address=stamp.address,
            provider=stamp.provider,
            status="deleted",
        )
    except Exception as e:
        raise InvalidDeleteCacheRequestException()


@router.get("stamp", response=GetStampResponse)
def get_stamps(_, address):
    try:
        stamps = CeramicCache.objects.filter(deleted_at=None, address=address)
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


class CacaoVerifySubmit(Schema):
    issuer: str
    signatures: List[Dict]
    payload: str
    cid: List[int]
    cacao: List[int]


class FailedVerificationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to authorize request"


class DbCacheToken(RefreshToken):
    # Lifetime of the token is set to 7 days (because this is the setting of the CACAO session)
    # But it should ideally be read out of the cacao
    lifetime: timedelta = timedelta(days=7)


class AcessTokenResponse(Schema):
    access: str


@router.post(
    "authenticate",
    response=AcessTokenResponse,
)
def authenticate(request, payload: CacaoVerifySubmit):
    """
    This method will validat a jws created with DagJWS, will validate by forwarding this to our validator
    it and return a JWT token.
    """
    try:
        r = requests.post(
            settings.CERAMIC_CACHE_CACAO_VALIDATION_URL, json=payload.dict()
        )
        if r.status_code == 200:
            token = DbCacheToken()
            token["did"] = payload.issuer

            return {
                "ok": True,
                "access": str(token.access_token),
            }

        log.error(
            "Failed to validate did signature for: %s.\n%s\n%s",
            payload.dict(),
            r,
            r.text,
        )
        raise FailedVerificationException(detail=f"Verifier response: {str(r)}")

    except Exception as e:
        log.error("Failed authenticate request: '%s'", payload.dict(), exc_info=True)
        raise e
