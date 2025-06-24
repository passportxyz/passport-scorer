"""Utility functions for Human Points functionality"""

from typing import Dict, Optional

from django.db import transaction
from django.db.models import F

from registry.models import (
    HumanPoints,
    HumanPointsConfig,
    HumanPointsMultiplier,
    HumanPointsCommunityQualifiedUsers,
)


# Map stamp providers to Human Points actions
STAMP_PROVIDER_TO_ACTION = {
    "humanKeysProvider": HumanPoints.Action.HUMAN_KEYS,
    "gtcStakingBronze": HumanPoints.Action.IDENTITY_STAKING_BRONZE,
    "gtcStakingSilver": HumanPoints.Action.IDENTITY_STAKING_SILVER,
    "gtcStakingGold": HumanPoints.Action.IDENTITY_STAKING_GOLD,
    "BeginnerCommunityStaker": HumanPoints.Action.COMMUNITY_STAKING_BEGINNER,
    "ExperiencedCommunityStaker": HumanPoints.Action.COMMUNITY_STAKING_EXPERIENCED,
    "TrustedCitizen": HumanPoints.Action.COMMUNITY_STAKING_TRUSTED,
}


async def aget_user_points_data(address: str) -> Dict:
    """
    Get user's points data including total points, breakdown, and eligibility
    """
    # Get all actions for this address
    actions = HumanPoints.objects.filter(address=address).select_related()
    
    # Get multiplier
    try:
        multiplier = await HumanPointsMultiplier.objects.aget(address=address)
        mult_value = multiplier.multiplier
    except HumanPointsMultiplier.DoesNotExist:
        mult_value = 1
    
    # Calculate points
    points_breakdown = {}
    total_points = 0
    
    async for action in actions:
        try:
            config = await HumanPointsConfig.objects.aget(
                action=action.action, active=True
            )
            points = config.points * mult_value
            points_breakdown[action.action] = points
            total_points += points
        except HumanPointsConfig.DoesNotExist:
            # Skip if no config found
            continue
    
    # Check eligibility (has at least 1 passing score)
    is_eligible = await HumanPointsCommunityQualifiedUsers.objects.filter(
        address=address
    ).aexists()
    
    return {
        "total_points": total_points,
        "is_eligible": is_eligible,
        "multiplier": mult_value,
        "breakdown": points_breakdown,
    }


async def arecord_stamp_actions(address: str, valid_stamps: list) -> None:
    """
    Record Human Points actions based on valid stamps
    """
    for stamp in valid_stamps:
        provider = stamp.get("provider")
        action = STAMP_PROVIDER_TO_ACTION.get(provider)
        
        if action:
            # For Human Keys, store nullifier in tx_hash field
            tx_hash = None
            if provider == "humanKeysProvider":
                # Extract nullifier from credential following the same pattern as deduplication
                credential = stamp.get("credential", {})
                credential_subject = credential.get("credentialSubject", {})
                
                # Check for hash first (standard case), then nullifiers array (multi-nullifier case)
                if "hash" in credential_subject:
                    tx_hash = credential_subject["hash"]
                elif "nullifiers" in credential_subject:
                    # For multi-nullifier case, use the first nullifier
                    nullifiers = credential_subject["nullifiers"]
                    if nullifiers and isinstance(nullifiers, list):
                        tx_hash = nullifiers[0]
            
            # Use get_or_create to handle duplicates gracefully
            await HumanPoints.objects.aget_or_create(
                address=address,
                action=action,
                defaults={"tx_hash": tx_hash}
            )


async def acheck_and_award_scoring_bonus(address: str, community_id: int) -> bool:
    """
    Check if user qualifies for scoring bonus (3+ passing scores)
    Returns True if bonus was newly awarded
    """
    # Check current passing scores count
    qualified_count = await HumanPointsCommunityQualifiedUsers.objects.filter(
        address=address
    ).acount()
    
    # Check if bonus already exists
    bonus_exists = await HumanPoints.objects.filter(
        address=address,
        action=HumanPoints.Action.SCORING_BONUS
    ).aexists()
    
    # Award bonus if qualified and not already awarded
    if qualified_count >= 3 and not bonus_exists:
        await HumanPoints.objects.acreate(
            address=address,
            action=HumanPoints.Action.SCORING_BONUS
        )
        return True
    
    return False


async def arecord_passing_score(address: str, community_id: int) -> None:
    """
    Record that an address achieved a passing score in a community
    """
    await HumanPointsCommunityQualifiedUsers.objects.aget_or_create(
        address=address,
        community_id=community_id
    )