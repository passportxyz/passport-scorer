"""Ceramic Cache API"""

# from ceramic_cache.models import CeramicCache
# from django.shortcuts import get_object_or_404

# Ninja
from ninja import Router, Schema
from ninja.security import HttpBearer

router = Router()


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        if token == "supersecret":
            return token


class CacheStampPayload(Schema):
    address: str
    provider: str
    stamp: str


@router.post("/stamp", auth=AuthBearer())
def cache_stamp(request, payload: CacheStampPayload):
    # import pdb

    # pdb.set_trace()
    print(payload, request)
    return
