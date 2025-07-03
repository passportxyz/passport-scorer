"""Utility functions for Human Points functionality"""

from typing import Dict

from django.db import connection
from django.db.models import F

from registry.models import (
    HumanPoints,
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


def get_user_points_data(address: str) -> Dict:
    """
    Get user's total points with breakdown using raw SQL for efficiency.
    Returns total points, eligibility status, multiplier, and points breakdown.
    """
    # Single query to get total points, multiplier, and breakdown
    query = """
        SELECT
            hp.address,
            hp.action,
            hp.chain_id,
            SUM(hpc.points * COALESCE(hpm.multiplier, 1)) as action_points,
            MAX(COALESCE(hpm.multiplier, 1)) as multiplier
        FROM registry_humanpoints hp
        INNER JOIN registry_humanpointsconfig hpc
            ON hp.action = hpc.action AND hpc.active = true
        LEFT JOIN registry_humanpointsmultiplier hpm
            ON hp.address = hpm.address
        WHERE hp.address = %s
        GROUP BY hp.address, hp.action, hp.chain_id
    """

    total_points = 0
    multiplier = 1
    breakdown = {}

    with connection.cursor() as cursor:
        cursor.execute(query, [address])
        rows = cursor.fetchall()
        multiplier = rows[0][4] if rows else 1

        for row in rows:
            points = row[3]
            total_points += points
            chain_id = row[2]
            breakdown_key = row[1]

            if chain_id:
                breakdown[f"{breakdown_key}_{chain_id}"] = points
                breakdown[breakdown_key] = (
                    points
                    if breakdown_key not in breakdown
                    else breakdown[breakdown_key] + points
                )
            else:
                breakdown[breakdown_key] = points

    # Check eligibility separately (single query)
    is_eligible = HumanPointsCommunityQualifiedUsers.objects.filter(
        address=address
    ).exists()

    return {
        "total_points": total_points,
        "is_eligible": is_eligible,
        "multiplier": multiplier,
        "breakdown": breakdown,
    }


async def arecord_stamp_actions(address: str, valid_stamps: list) -> None:
    """
    Record Human Points actions based on valid stamps - optimized bulk version
    """
    from asgiref.sync import sync_to_async

    # Collect all HumanPoints objects to create
    objects_to_create = []

    for stamp in valid_stamps:
        # Check for Human Keys
        credential = stamp.get("credential", {})
        credential_subject = credential.get("credentialSubject", {})
        nullifiers = credential_subject.get("nullifiers", [])

        if isinstance(nullifiers, list):
            for nullifier in nullifiers:
                if nullifier and str(nullifier).startswith("v1"):
                    objects_to_create.append(
                        HumanPoints(
                            address=address,
                            action=HumanPoints.Action.HUMAN_KEYS,
                            tx_hash=nullifier,
                        )
                    )
                    break

        # Check for provider-based actions
        provider = stamp.get("provider")
        action = STAMP_PROVIDER_TO_ACTION.get(provider)
        if action:
            objects_to_create.append(
                HumanPoints(address=address, action=action, tx_hash=None)
            )

    # Bulk create all at once, let DB handle conflicts
    if objects_to_create:
        # sync_to_async needed - Django doesn't provide async bulk_create
        await sync_to_async(HumanPoints.objects.bulk_create)(
            objects_to_create, ignore_conflicts=True
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

    # Award bonus if qualified (let DB handle conflicts)
    if qualified_count >= 3:
        _, created = await HumanPoints.objects.aget_or_create(
            address=address, action=HumanPoints.Action.SCORING_BONUS
        )
        return created

    return False


async def arecord_passing_score(address: str, community_id: int) -> None:
    """
    Record that an address achieved a passing score in a community
    """
    await HumanPointsCommunityQualifiedUsers.objects.aget_or_create(
        address=address, community_id=community_id
    )
