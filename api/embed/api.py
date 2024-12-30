from typing import Any, List

from asgiref.sync import async_to_sync
from ninja import Router, Schema
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from account.models import Community
from ceramic_cache.api.schema import (
    CacheStampPayload,
    GetStampsWithV2ScoreResponse,
)
from ceramic_cache.api.v1 import handle_add_stamps_only
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
from trusta_labs.api import CgrantsApiKey
from v2.api import handle_scoring

api_router = Router()

api = NinjaExtraAPI(
    urls_namespace="embed",
    title="Internal API",
    description="Endpoints for internal use.",
)


api.add_router("", api_router)

log = logging.getLogger(__name__)


internal_api_key = CgrantsApiKey()


class AddStampsPayload(Schema):
    scorer_id: int
    stamps: List[Any]


# TODO: check authentication for these endpoints. Ideally the embed service requires an internal API key, but the lambda one is only exposed on internal LB
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
    address_lower = address.lower()
    if not is_valid_address(address_lower):
        raise InvalidAddressException()

    print("post stamps to ", address_lower)
    add_stamps_payload = [
        CacheStampPayload(
            address=address_lower,
            provider=stamp.get("credentialSubject", {}).get("provider"),
            stamp=stamp,
        )
        for stamp in payload.stamps
    ]
    print("post payload.scorer_id ", payload.scorer_id)

    try:
        added_stamps = handle_add_stamps_only(
            address, add_stamps_payload, payload.scorer_id
        )
        user_account = Community.objects.get(id=payload.scorer_id).account
        score = async_to_sync(handle_scoring)(address, payload.scorer_id, user_account)

        return GetStampsWithV2ScoreResponse(**added_stamps.model_dump(), score=score)
    except Exception as e:
        # TODO: log exception and handle error properly
        print("Error in add_stamps:", e)
        import traceback

        traceback.print_exc()
        raise e


class AccountAPIKeySchema(Schema):
    rate_limit: str


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
    """
    Return the capabilities allocated to this API key.
    This API is intended to be used in the embed service in the passport repo
    """
    return AccountAPIKeySchema.from_orm(request.api_key)
