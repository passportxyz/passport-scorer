"""Ceramic Cache API"""

from django.conf import settings
from ninja import Router, Schema
from ninja.security import HttpBearer
from .exceptions import InvalidDeleteCacheRequestException

from .models import CeramicCache

router = Router()


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        if token == settings.CERAMIC_CACHE_BEARER_TOKEN:
            return token


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


@router.post(
    "stamp",
    auth=AuthBearer(),
    response={201: CachedStampResponse},
)
def cache_stamp(request, payload: CacheStampPayload):
    try:
        stamp, created = CeramicCache.objects.update_or_create(
            address=payload.address,
            provider=payload.provider,
            defaults=dict(
                stamp=payload.stamp,
                deleted_at=False,
            ),
        )
        return stamp
    except Exception as e:
        raise e


@router.delete(
    "stamp",
    auth=AuthBearer(),
    response=DeleteStampResponse,
)
def soft_delete_stamp(request, payload: DeleteStampPayload):
    try:
        stamp = CeramicCache.objects.get(
            address=payload.address,
            provider=payload.provider,
        )
        stamp.deleted_at = True
        stamp.save()

        return DeleteStampResponse(
            address=stamp.address,
            provider=stamp.provider,
            status="deleted",
        )
    except Exception as e:
        raise InvalidDeleteCacheRequestException()
