from typing import List

from django.conf import settings
from ninja import Router, Schema
from ninja.security import APIKeyHeader
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from ceramic_cache.api.schema import (
    CacheStampPayload,
    GetStampsWithScoreResponse,
)
from ceramic_cache.api.v1 import handle_add_stamps
from registry.api.schema import (
    ErrorMessageResponse,
)
from registry.api.utils import (
    is_valid_address,
)
from registry.exceptions import (
    InvalidAddressException,
)
from v2.schema import V2ScoreResponse

from .schema.eip712 import VerifiableEip712Credential

api_router = Router()

api = NinjaExtraAPI(
    urls_namespace="internal",
    title="Internal API",
    description="Endpoints for internal use.",
)


api.add_router("", api_router)

log = logging.getLogger(__name__)


class InternalApiKey(APIKeyHeader):
    param_name = "AUTHORIZATION"

    def authenticate(self, request, key):
        if key == settings.INTERNAL_API_KEY:
            return key
        return None


class AddStampsPayload(Schema):
    scorer_id: int
    stamps: List[VerifiableEip712Credential]


@api_router.post(
    "/stamps/{str:address}",
    auth=InternalApiKey(),
    response={
        201: GetStampsWithScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Add Stamps and get the new score",
)
def add_stamps(request, address: str, payload: AddStampsPayload) -> V2ScoreResponse:
    address_lower = address.lower()
    if not is_valid_address(address_lower):
        raise InvalidAddressException()

    cacheStampPayloads = [
        CacheStampPayload(
            address=address_lower,
            provider=stamp.credentialSubject.provider,
            stamp=stamp.dict(),
        )
        for stamp in payload.stamps
    ]

    return handle_add_stamps(address, cacheStampPayloads, payload.scorer_id)
