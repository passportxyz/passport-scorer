from typing import Any, List, Optional

from asgiref.sync import async_to_sync
from django.conf import settings
from ninja import Router, Schema
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from account.models import (
    Community,
    Customization,
    EmbedSectionOrder,
    EmbedStampPlatform,
)
from ceramic_cache.api.schema import (
    CacheStampPayload,
    GetStampsWithV2ScoreResponse,
)
from ceramic_cache.api.v1 import handle_add_stamps_only
from ceramic_cache.models import CeramicCache
from registry.api.utils import (
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
    embed_rate_limit: str | None


def handle_validate_embed_api_key(request) -> AccountAPIKeySchema:
    """
    Return the capabilities allocated to this API key.
    This API is intended to be used in the embed service in the passport repo
    """
    return AccountAPIKeySchema.from_orm(request.api_key)


def handle_get_score(scorer_id: str, address: str) -> GetStampsWithV2ScoreResponse:
    """
    Get the score for a given address and scorer_id
    """
    try:
        if int(scorer_id) < 0:
            scorer_id = settings.DEMO_API_SCORER_ID
    except ValueError:
        pass

    address_lower = address.lower()

    user_account = Community.objects.get(id=scorer_id).account

    score = async_to_sync(handle_scoring_for_account)(
        address_lower, scorer_id, user_account
    )

    return GetStampsWithV2ScoreResponse(
        success=True,
        score=score,
        stamps=CeramicCache.objects.filter(
            address=address_lower,
            type=CeramicCache.StampType.V1,
            deleted_at__isnull=True,
            revocation__isnull=True,
        ),
    )


class EmbedStampSectionItemSchema(Schema):
    """Schema for individual stamp items within a section"""
    platform_id: str
    order: int


class EmbedStampSectionSchema(Schema):
    """Schema for stamp sections with their items"""
    title: str
    order: int
    items: List[EmbedStampSectionItemSchema]


class EmbedConfigResponse(Schema):
    """Combined response for embed configuration"""
    weights: dict[str, float]
    stamp_sections: List[EmbedStampSectionSchema]


def handle_get_embed_stamp_sections(community_id: str) -> List[EmbedStampSectionSchema]:
    """
    Get customized stamp sections for a given community/scorer.
    Returns an empty list if no sections exist.
    """
    try:
        customization = Customization.objects.get(scorer_id=community_id)
    except Customization.DoesNotExist:
        return []

    try:
        section_orders = EmbedSectionOrder.objects.filter(
            customization=customization
        ).select_related('section').order_by('order', 'id')

        platforms = EmbedStampPlatform.objects.filter(
            customization=customization
        ).select_related('section', 'platform').order_by('order', 'id')

        # Group platforms by section header id
        platforms_by_section = {}
        for p in platforms:
            platforms_by_section.setdefault(p.section_id, []).append(p)

        result = []
        for so in section_orders:
            section_platforms = platforms_by_section.get(so.section_id, [])
            items = [
                EmbedStampSectionItemSchema(
                    platform_id=p.platform.platform_id,
                    order=p.order,
                )
                for p in section_platforms
            ]
            result.append(
                EmbedStampSectionSchema(
                    title=so.section.name,
                    order=so.order,
                    items=items,
                )
            )

        return result
    except Exception as e:
        log.error(f"Error fetching embed stamp sections for community {community_id}: {e}")
        return []


def handle_get_embed_config(community_id: str) -> EmbedConfigResponse:
    """
    Get combined embed configuration: weights and stamp sections.
    Returns weights with empty stamp_sections if sections lookup fails (partial data).
    """
    from ceramic_cache.api.v1 import handle_get_scorer_weights

    weights = handle_get_scorer_weights(community_id)
    stamp_sections = handle_get_embed_stamp_sections(community_id)

    return EmbedConfigResponse(weights=weights, stamp_sections=stamp_sections)
