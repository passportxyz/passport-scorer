"""Ceramic Cache API"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type

import requests
from account.models import Nonce
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest
from ninja import Router, Schema
from ninja_extra import status
from ninja_extra.exceptions import APIException
from ninja_extra.security import HttpBearer
from ninja_jwt.authentication import InvalidToken

# from ninja_jwt.schema import RefreshToken
from ninja_jwt.settings import api_settings
from ninja_jwt.tokens import RefreshToken, Token, TokenError
from ninja_schema import Schema

from .exceptions import (
    InvalidDeleteCacheRequestException,
    InvalidSessionException,
    TooManyStampsException,
)
from .models import CeramicCache
from .utils import validate_dag_jws_payload

log = logging.getLogger(__name__)

router = Router()


def get_utc_time():
    return datetime.utcnow()


def get_did(address: str):
    return f"did:pkh:eip155:1:{address.lower()}"


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


class DeleteStampResponse(Schema):
    address: str
    provider: str
    status: str


class BulkDeleteResponse(Schema):
    status: str


class CachedStampResponse(Schema):
    address: str
    provider: str
    stamp: Any


class GetStampResponse(Schema):
    success: bool
    stamps: List[CachedStampResponse]


@router.post(
    "stamps/bulk", response={201: List[CachedStampResponse]}, auth=JWTDidAuth()
)
def cache_stamps(request, payload: List[CacheStampPayload]):
    try:
        if len(payload) > settings.MAX_BULK_CACHE_SIZE:
            raise TooManyStampsException()

        address = get_address_from_did(request.did)
        stamp_objects = []
        for p in payload:
            stamp_object = CeramicCache(
                address=address,
                provider=p.provider,
                stamp=p.stamp,
            )
            stamp_objects.append(stamp_object)
        created = CeramicCache.objects.bulk_create(
            stamp_objects,
            update_conflicts=True,
            update_fields=["stamp"],
            unique_fields=["address", "provider"],
        )
        return created
    except Exception as e:
        raise e


@router.delete("stamps/bulk", response=BulkDeleteResponse, auth=JWTDidAuth())
def delete_stamps(request, payload: List[DeleteStampPayload]):
    try:
        if len(payload) > settings.MAX_BULK_CACHE_SIZE:
            raise TooManyStampsException()

        stamps = CeramicCache.objects.filter(
            address=get_address_from_did(request.did),
            provider__in=[p.provider for p in payload],
        )
        if not stamps:
            raise InvalidDeleteCacheRequestException()
        stamps.delete()

        return {"status": "success"}
    except Exception as e:
        raise e


@router.post(
    "stamp",
    response={201: CachedStampResponse},
    auth=JWTDidAuth(),
)
def cache_stamp(request, payload: CacheStampPayload):
    try:
        if request.did.lower() != get_did(payload.address):
            raise InvalidSessionException()
        stamp, created = CeramicCache.objects.update_or_create(
            address=payload.address,
            provider=payload.provider,
            defaults=dict(
                stamp=payload.stamp,
            ),
        )
        return stamp
    except Exception as e:
        raise e


@router.delete(
    "stamp",
    response=DeleteStampResponse,
    auth=JWTDidAuth(),
)
def delete_stamp(request, payload: DeleteStampPayload):
    try:
        if request.did.lower() != get_did(payload.address):
            raise InvalidSessionException()

        stamp = CeramicCache.objects.get(
            address=payload.address,
            provider=payload.provider,
        )

        address = stamp.address
        provider = stamp.provider

        stamp.delete()

        return DeleteStampResponse(
            address=address,
            provider=provider,
            status="deleted",
        )
    except Exception as e:
        raise InvalidDeleteCacheRequestException()


@router.get("stamp", response=GetStampResponse)
def get_stamps(request, address):
    try:
        stamps = CeramicCache.objects.filter(address=address)
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
    nonce: str
    cid: List[int]
    cacao: List[int]


class FailedVerificationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to authorize request"


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
        r = requests.post(
            settings.CERAMIC_CACHE_CACAO_VALIDATION_URL, json=payload.dict(), timeout=30
        )
        if r.status_code == 200:
            token = DbCacheToken()
            token["did"] = payload.issuer

            return {
                "access": str(token.access_token),
            }

        log.error(
            "Failed to validate did signature for: %s.\n%s\n%s",
            payload.dict(),
            r,
            r.text,
        )
        raise FailedVerificationException(detail=f"Verifier response: {str(r)}")

    except APIException:
        # re-raise API exceptions
        raise
    except Exception as esc:
        log.error("Failed authenticate request: '%s'", payload.dict(), exc_info=True)
        raise APIException(detail=f"Failed authenticate request: {str(esc)}") from esc
