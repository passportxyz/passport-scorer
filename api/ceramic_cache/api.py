"""Ceramic Cache API"""

# from ceramic_cache.models import CeramicCache
# from django.shortcuts import get_object_or_404

from django.conf import settings
from django.db import IntegrityError
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
    response={201: CachedStampResponse, 409: {"error": str}},
)
def cache_stamp(request, payload: CacheStampPayload):
    try:
        cached_stamp = CeramicCache.objects.create(
            address=payload.address, provider=payload.provider, stamp=payload.stamp
        )

        return cached_stamp
    except IntegrityError as e:
        return {"error": "Stamp already exists"}
