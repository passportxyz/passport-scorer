"""Ceramic Cache API"""

# from ceramic_cache.models import CeramicCache
# from django.shortcuts import get_object_or_404

from django.conf import settings
from ninja import Router, Schema
from ninja.security import HttpBearer

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
        existing_stamp = CeramicCache.objects.filter(
            provider=payload.provider, address=payload.address
        )
        if existing_stamp.exists():
            existing_stamp = existing_stamp.first()
            existing_stamp.stamp = payload.stamp
            existing_stamp.save()
            return existing_stamp

        cached_stamp = CeramicCache.objects.create(
            address=payload.address, provider=payload.provider, stamp=payload.stamp
        )
        return cached_stamp
    except Exception as e:
        raise e
