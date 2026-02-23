from typing import Any, List, Optional

from asgiref.sync import async_to_sync
from django.conf import settings
from ninja import Router, Schema
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from account.models import (
    Community,
    Customization,
    CustomPlatform,
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


class CustomStampSchema(Schema):
    """Schema for a single custom stamp (AllowList or DeveloperList)"""
    provider_id: str
    display_name: str
    description: Optional[str] = None
    weight: float


class CustomStampsSchema(Schema):
    """Custom stamps configured for this scorer (Guest List + Developer List)"""
    allow_list_stamps: List[CustomStampSchema] = []
    developer_list_stamps: List[CustomStampSchema] = []


class PlatformCredentialSchema(Schema):
    """A credential/provider within a platform definition."""
    id: str        # e.g. "AllowList#VIPList"
    weight: str    # e.g. "10.0"


class PlatformDefinitionSchema(Schema):
    """Full platform definition for custom stamps (and future standard overrides)."""
    platform_id: str           # Unique ID: "AllowList#VIPList" or "DeveloperList#Repo#hash"
    icon_platform_id: str      # Base platform for icon lookup: "AllowList" or "CustomGithub"
    name: str                  # Display name
    description: str
    documentation_link: Optional[str] = None
    requires_signature: bool = False
    requires_popup: bool = False
    popup_url: Optional[str] = None
    requires_sdk_flow: bool = False
    credentials: List[PlatformCredentialSchema] = []


class EmbedConfigResponse(Schema):
    """Combined response for embed configuration"""
    weights: dict[str, float]
    stamp_sections: List[EmbedStampSectionSchema]
    platforms: List[PlatformDefinitionSchema] = []
    custom_stamps: CustomStampsSchema = CustomStampsSchema(
        allow_list_stamps=[], developer_list_stamps=[]
    )


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


def handle_get_custom_stamps(community_id: str) -> CustomStampsSchema:
    """
    Get custom stamps (AllowList / Guest List and Developer List) for this community.
    These are configured at the Customization level and surfaced in Embed.
    """
    try:
        customization = Customization.objects.get(scorer_id=community_id)
    except Customization.DoesNotExist:
        return CustomStampsSchema(allow_list_stamps=[], developer_list_stamps=[])

    allow_list_stamps = [
        CustomStampSchema(
            provider_id=f"AllowList#{al.address_list.name}",
            display_name=al.address_list.name,
            description="Verify you are part of this community.",
            weight=float(al.weight),
        )
        for al in customization.allow_lists.select_related("address_list").all()
    ]

    developer_list_stamps = [
        CustomStampSchema(
            provider_id=cc.ruleset.provider_id,
            display_name=cc.display_name,
            description=cc.description or "",
            weight=float(cc.weight),
        )
        for cc in customization.custom_credentials.select_related("platform", "ruleset").filter(
            platform__platform_type=CustomPlatform.PlatformType.DeveloperList
        )
    ]

    return CustomStampsSchema(
        allow_list_stamps=allow_list_stamps,
        developer_list_stamps=developer_list_stamps,
    )


def handle_get_platforms(community_id: str) -> List[PlatformDefinitionSchema]:
    """
    Build PlatformDefinition objects for custom stamps.
    These are custom stamps that need full platform metadata because
    they don't exist in the embed service's static STAMP_PAGES.
    """
    try:
        customization = Customization.objects.get(scorer_id=community_id)
    except Customization.DoesNotExist:
        return []

    platform_defs = []

    # AllowList stamps
    for al in customization.allow_lists.select_related("address_list").all():
        provider_id = f"AllowList#{al.address_list.name}"
        platform_defs.append(
            PlatformDefinitionSchema(
                platform_id=provider_id,
                icon_platform_id="AllowList",
                name=al.address_list.name,
                description="Verify you are part of this community.",
                documentation_link="https://support.passport.xyz/passport-knowledge-base/stamps/how-do-i-add-passport-stamps/the-guest-list-stamp",
                credentials=[
                    PlatformCredentialSchema(
                        id=provider_id,
                        weight=str(float(al.weight)),
                    )
                ],
            )
        )

    # DeveloperList stamps
    for cc in customization.custom_credentials.select_related("platform", "ruleset").filter(
        platform__platform_type=CustomPlatform.PlatformType.DeveloperList
    ):
        platform_defs.append(
            PlatformDefinitionSchema(
                platform_id=cc.ruleset.provider_id,
                icon_platform_id="CustomGithub",
                name=cc.display_name,
                description=cc.description or "Verify your GitHub contributions meet the requirements.",
                documentation_link="https://support.passport.xyz/passport-knowledge-base/stamps/how-do-i-add-passport-stamps/the-developer-list-stamp",
                requires_signature=True,
                requires_popup=True,
                credentials=[
                    PlatformCredentialSchema(
                        id=cc.ruleset.provider_id,
                        weight=str(float(cc.weight)),
                    )
                ],
            )
        )

    return platform_defs


def handle_get_embed_config(community_id: str) -> EmbedConfigResponse:
    """
    Get combined embed configuration: weights, stamp sections, platforms, and custom stamps.
    The `platforms` field provides full definitions for custom stamps.
    Custom stamps are auto-appended to stamp_sections so they appear in the section list.
    The `custom_stamps` field is kept for backward compatibility.
    """
    from ceramic_cache.api.v1 import handle_get_scorer_weights

    weights = handle_get_scorer_weights(community_id)
    stamp_sections = handle_get_embed_stamp_sections(community_id)
    custom_stamps = handle_get_custom_stamps(community_id)
    platform_defs = handle_get_platforms(community_id)

    # Auto-append custom stamps into stamp_sections grouped by type
    allow_list_items = []
    developer_list_items = []
    for i, pdef in enumerate(platform_defs):
        item = EmbedStampSectionItemSchema(
            platform_id=pdef.platform_id,
            order=i,
        )
        if pdef.icon_platform_id == "AllowList":
            allow_list_items.append(item)
        else:
            developer_list_items.append(item)

    next_order = max((s.order for s in stamp_sections), default=-1) + 1

    if allow_list_items:
        stamp_sections.append(
            EmbedStampSectionSchema(
                title="Guest List",
                order=next_order,
                items=allow_list_items,
            )
        )
        next_order += 1

    if developer_list_items:
        stamp_sections.append(
            EmbedStampSectionSchema(
                title="Developer List",
                order=next_order,
                items=developer_list_items,
            )
        )

    return EmbedConfigResponse(
        weights=weights,
        stamp_sections=stamp_sections,
        platforms=platform_defs,
        custom_stamps=custom_stamps,
    )
