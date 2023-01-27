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
        stamp, created = CeramicCache.objects.update_or_create(
            address=payload.address,
            provider=payload.provider,
            defaults={"stamp": payload.stamp},
        )

        return stamp
    except Exception as e:
        raise e
