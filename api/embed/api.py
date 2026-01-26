from typing import Any, List, Optional

from asgiref.sync import async_to_sync
from django.conf import settings
from ninja import Router, Schema
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from account.models import Community, EmbedStampSection
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
    Returns an empty list if no customization exists.
    """
    try:
        community = Community.objects.get(id=community_id)
        
        # Check if this community has a customization
        if not hasattr(community, 'customization'):
            return []
        
        customization = community.customization
        
        # Get all sections with their items, ordered by section order
        sections = EmbedStampSection.objects.filter(
            customization=customization
        ).prefetch_related('items').order_by('order', 'id')
        
        # Build the response
        result = []
        for section in sections:
            items = [
                EmbedStampSectionItemSchema(
                    platform_id=item.platform_id,
                    order=item.order
                )
                for item in section.items.all().order_by('order', 'id')
            ]
            
            result.append(
                EmbedStampSectionSchema(
                    title=section.title,
                    order=section.order,
                    items=items
                )
            )
        
        return result
    except Community.DoesNotExist:
        return []
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
