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


class PlatformCredentialSchema(Schema):
    """A credential/provider within a platform definition."""
    id: str        # e.g. "AllowList#VIPList"
    weight: str    # e.g. "10.0"


class PlatformDefinitionSchema(Schema):
    """Full platform definition for custom stamps (and future standard overrides)."""
    platform_id: str           # Unique ID: CustomPlatform.name or "AllowList#VIPList"
    icon_platform_id: str      # Base platform for icon lookup: "AllowList" or "CustomGithub"
    name: str                  # Display name
    description: str
    is_evm: bool = False
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


def handle_get_embed_stamp_sections(
    community_id: str, customization: Optional[Customization] = None
) -> List[EmbedStampSectionSchema]:
    """
    Get customized stamp sections for a given community/scorer.
    Returns an empty list if no sections exist.
    """
    if customization is None:
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


PLATFORM_TYPE_DEFAULTS = {
    CustomPlatform.PlatformType.DeveloperList: {
        "icon_platform_id": "CustomGithub",
        "description": "Verify your GitHub contributions meet the requirements.",
        "requires_signature": True,
        "requires_popup": True,
    },
    CustomPlatform.PlatformType.NFTHolder: {
        "icon_platform_id": "NFT",
        "description": "Verify NFT ownership.",
        "requires_signature": False,
        "requires_popup": False,
    },
}


def _build_platform_def(
    platform: CustomPlatform, credentials: list[PlatformCredentialSchema]
) -> PlatformDefinitionSchema:
    """Build a PlatformDefinitionSchema from a CustomPlatform and its credentials."""
    defaults = PLATFORM_TYPE_DEFAULTS.get(platform.platform_type, {})
    return PlatformDefinitionSchema(
        platform_id=platform.name,
        icon_platform_id=defaults.get("icon_platform_id", "AllowList"),
        name=platform.display_name or platform.name,
        description=platform.description or defaults.get("description", ""),
        is_evm=platform.is_evm,
        requires_signature=defaults.get("requires_signature", False),
        requires_popup=defaults.get("requires_popup", False),
        credentials=credentials,
    )


def handle_get_platforms(
    community_id: str, customization: Optional[Customization] = None
) -> List[PlatformDefinitionSchema]:
    """
    Build PlatformDefinition objects for custom stamps, grouped by CustomPlatform.

    Credentials (CustomCredentials and AllowLists with a platform set) are grouped
    under their CustomPlatform. Standalone AllowLists (platform=None) each become
    their own platform entry.
    """
    if customization is None:
        try:
            customization = Customization.objects.get(scorer_id=community_id)
        except Customization.DoesNotExist:
            return []

    # 1. Collect credentials grouped by CustomPlatform
    platform_credentials: dict[int, tuple[CustomPlatform, list[PlatformCredentialSchema]]] = {}

    for cc in customization.custom_credentials.select_related("platform", "ruleset").all():
        pk = cc.platform_id
        if pk not in platform_credentials:
            platform_credentials[pk] = (cc.platform, [])
        platform_credentials[pk][1].append(
            PlatformCredentialSchema(
                id=cc.ruleset.provider_id,
                weight=str(float(cc.weight)),
            )
        )

    # 2. AllowLists with a platform assigned are added to the same group
    standalone_allow_lists = []
    for al in customization.allow_lists.select_related("address_list", "platform").all():
        provider_id = f"AllowList#{al.address_list.name}"
        cred = PlatformCredentialSchema(id=provider_id, weight=str(float(al.weight)))
        if al.platform_id is not None:
            pk = al.platform_id
            if pk not in platform_credentials:
                platform_credentials[pk] = (al.platform, [])
            platform_credentials[pk][1].append(cred)
        else:
            standalone_allow_lists.append((al, cred))

    # 3. Build platform definitions from grouped credentials
    platform_defs = []
    for _platform, creds in platform_credentials.values():
        platform_defs.append(_build_platform_def(_platform, creds))

    # 4. Standalone AllowLists (no platform) become their own entry
    for al, cred in standalone_allow_lists:
        platform_defs.append(
            PlatformDefinitionSchema(
                platform_id=cred.id,
                icon_platform_id="AllowList",
                name=al.address_list.name,
                description="Verify you are part of this community.",
                credentials=[cred],
            )
        )

    return platform_defs


def handle_get_embed_config(community_id: str) -> EmbedConfigResponse:
    """
    Get combined embed configuration: weights, stamp sections, and platforms.

    - weights: scorer weight per provider
    - stamp_sections: ordered sections of platform_ids (admin-configured)
    - platforms: full definitions for custom stamps (CustomPlatform + AllowList)
    """
    from ceramic_cache.api.v1 import handle_get_scorer_weights

    weights = handle_get_scorer_weights(community_id)

    try:
        customization = Customization.objects.get(scorer_id=community_id)
    except Customization.DoesNotExist:
        customization = None

    stamp_sections = handle_get_embed_stamp_sections(community_id, customization)
    platforms = handle_get_platforms(community_id, customization)

    return EmbedConfigResponse(
        weights=weights,
        stamp_sections=stamp_sections,
        platforms=platforms,
    )
