"""Ceramic Cache API"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, cast

import requests
from django.conf import settings
from ninja import Router, Schema
from ninja.security import APIKeyHeader
from ninja_extra import status
from ninja_extra.exceptions import APIException
from ninja_jwt.tokens import RefreshToken

from .exceptions import InvalidDeleteCacheRequestException
from .models import CeramicCache

log = logging.getLogger(__name__)

router = Router()


def get_utc_time():
    return datetime.utcnow()


class AuthAPIKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        if key == settings.CERAMIC_CACHE_API_KEY and key != "":
            return key


class CacheStampPayload(Schema):
    address: str
    provider: str
    stamp: str


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
    stamp: str


class GetStampResponse(Schema):
    success: bool
    stamps: List[CachedStampResponse]


@router.post(
    "stamp",
    auth=AuthAPIKey(),
    response={201: CachedStampResponse},
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
    auth=AuthAPIKey(),
    response=DeleteStampResponse,
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

        raise FailedVerificationException

    except Exception as e:
        log.error("Failed authenticate request: '%s'", payload.dict(), exc_info=True)
        raise e
