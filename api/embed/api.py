from typing import Any, Dict, List, Optional

from asgiref.sync import async_to_sync
from ninja import Router, Schema
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from account.models import Community
from ceramic_cache.api.schema import (
    CacheStampPayload,
    GetStampsWithV2ScoreResponse,
)
from ceramic_cache.api.v1 import handle_add_stamps_only, handle_get_scorer_weights
from ceramic_cache.models import CeramicCache
from internal.api_key import internal_api_key
from registry.api.schema import (
    ErrorMessageResponse,
)
from registry.api.utils import (
    ApiKey,
    is_valid_address,
)
from registry.exceptions import (
    InvalidAddressException,
)
from v2.api import handle_scoring_for_account

api_router = Router()

api = NinjaExtraAPI(
    urls_namespace="embed",
    title="Internal API",
    description="Endpoints for internal use.",
)


api.add_router("", api_router)

log = logging.getLogger(__name__)


class AddStampsPayload(Schema):
    scorer_id: int
    stamps: List[Any]


# Endpoint for this defined in internal module
# TODO 3280 Remove this endpoint
@api_router.post(
    "/stamps/{str:address}",
    auth=internal_api_key,
    response={
        200: GetStampsWithV2ScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Add Stamps and get the new score",
)
def add_stamps(
    request, address: str, payload: AddStampsPayload
) -> GetStampsWithV2ScoreResponse:
    return handle_embed_add_stamps(address, payload)


def handle_embed_add_stamps(
    address: str, payload: AddStampsPayload
) -> GetStampsWithV2ScoreResponse:
    address_lower = address.lower()
    if not is_valid_address(address_lower):
        raise InvalidAddressException()

    add_stamps_payload = [
        CacheStampPayload(
            address=address_lower,
            provider=stamp.get("credentialSubject", {}).get("provider"),
            stamp=stamp,
        )
        for stamp in payload.stamps
    ]

    try:
        added_stamps = handle_add_stamps_only(
            address, add_stamps_payload, CeramicCache.SourceApp.EMBED, payload.scorer_id
        )
        user_account = Community.objects.get(id=payload.scorer_id).account
        score = async_to_sync(handle_scoring_for_account)(
            address, payload.scorer_id, user_account
        )

        return GetStampsWithV2ScoreResponse(**added_stamps.model_dump(), score=score)
    except Exception as e:
        log.error("Error in add_stamps: %s", e)
        import traceback

        traceback.print_exc()
        raise e


class AccountAPIKeySchema(Schema):
    rate_limit: str | None


# TODO 3280 Remove this endpoint
@api_router.get(
    "/validate-api-key",
    # Here we want to authenticate the partners key, hence this ApiKey auth class
    auth=ApiKey(),
    response={
        200: AccountAPIKeySchema,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Add Stamps and get the new score",
)
def validate_api_key(request) -> AccountAPIKeySchema:
    return handle_validate_embed_api_key(request)


def handle_validate_embed_api_key(request) -> AccountAPIKeySchema:
    """
    Return the capabilities allocated to this API key.
    This API is intended to be used in the embed service in the passport repo
    """
    return AccountAPIKeySchema.from_orm(request.api_key)


# TODO 3280 Remove this endpoint
@api_router.get("/weights", response=Dict[str, float])
def get_embed_weights(request, community_id: Optional[str] = None) -> Dict[str, float]:
    """
    ---
    get:
      description: Get embed weights
      responses:
        200:
          description: Returns the embed weights
    """
    return handle_get_scorer_weights(community_id)
