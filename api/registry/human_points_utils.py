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
        # First check if this stamp has a v1 nullifier (Human Key)
        credential = stamp.get("credential", {})
        credential_subject = credential.get("credentialSubject", {})
        nullifiers = credential_subject.get("nullifiers", [])
        
        v1_nullifier = None
        if isinstance(nullifiers, list):
            for nullifier in nullifiers:
                if nullifier and str(nullifier).startswith("v1"):
                    v1_nullifier = nullifier
                    break
        
        if v1_nullifier:
            await HumanPoints.objects.aget_or_create(
                address=address,
                action=HumanPoints.Action.HUMAN_KEYS,
                defaults={"tx_hash": v1_nullifier}
            )
        
        # Check for provider-based actions
        provider = stamp.get("provider")
        action = STAMP_PROVIDER_TO_ACTION.get(provider)
        
        if action:
            # Use get_or_create to handle duplicates gracefully
            await HumanPoints.objects.aget_or_create(
                address=address,
                action=action,
                defaults={"tx_hash": None}
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
