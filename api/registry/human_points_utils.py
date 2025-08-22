"""Utility functions for Human Points functionality"""

from typing import Dict

from django.conf import settings
from django.db import connection
from django.db.models import F

from account.models import AddressList
from registry.models import (
    HumanPoints,
    HumanPointsCommunityQualifiedUsers,
    HumanPointsConfig,
)

# Map stamp providers to Human Points actions
STAMP_PROVIDER_TO_ACTION = {
    "SelfStakingBronze": HumanPoints.Action.IDENTITY_STAKING_BRONZE,
    "SelfStakingSilver": HumanPoints.Action.IDENTITY_STAKING_SILVER,
    "SelfStakingGold": HumanPoints.Action.IDENTITY_STAKING_GOLD,
    "BeginnerCommunityStaker": HumanPoints.Action.COMMUNITY_STAKING_BEGINNER,
    "ExperiencedCommunityStaker": HumanPoints.Action.COMMUNITY_STAKING_EXPERIENCED,
    "TrustedCitizen": HumanPoints.Action.COMMUNITY_STAKING_TRUSTED,
    "HolonymGovIdProvider": HumanPoints.Action.HUMAN_TECH_GOV_ID,
    "HolonymPhone": HumanPoints.Action.HUMAN_TECH_PHONE,
    "CleanHands": HumanPoints.Action.HUMAN_TECH_PROOF_OF_CLEAN_HANDS,
    "Biometrics": HumanPoints.Action.HUMAN_TECH_BIOMETRIC,
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
            SUM(hpc.points) as action_points,
            MAX(COALESCE(hpm.multiplier, 1)) as multiplier
        FROM registry_humanpoints hp
        INNER JOIN registry_humanpointsconfig hpc
            ON hp.action = hpc.action AND hpc.active = true
        LEFT JOIN registry_humanpointsmultiplier hpm
            ON hp.address = hpm.address
        WHERE hp.address = %s
            AND hp.action != 'HIM'
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
    Uses provider as key for deduplication since nullifiers can rotate after 6 months
    """
    from asgiref.sync import sync_to_async

    # Collect all HumanPoints objects to create
    objects_to_create = []

    for stamp in valid_stamps:
        # Check for Human Keys
        credential = stamp.get("credential", {})
        credential_subject = credential.get("credentialSubject", {})
        nullifiers = credential_subject.get("nullifiers", [])

        # Process Human Keys if we have at least one valid nullifier and a provider
        if isinstance(nullifiers, list) and any(nullifiers):
            credential_provider = credential_subject.get("provider")

            if credential_provider:
                # Check if this provider already exists in the database
                existing_record = await HumanPoints.objects.filter(
                    address=address,
                    action=HumanPoints.Action.HUMAN_KEYS,
                    provider=credential_provider,
                ).afirst()

                # Only create if no existing record for this provider
                if not existing_record:
                    # Use the latest valid nullifier (last one in array)
                    latest_nullifier = next(
                        (n for n in reversed(nullifiers) if n), None
                    )
                    if latest_nullifier:
                        objects_to_create.append(
                            HumanPoints(
                                address=address,
                                action=HumanPoints.Action.HUMAN_KEYS,
                                tx_hash=latest_nullifier,
                                provider=credential_provider,
                            )
                        )

        # Check for provider-based actions
        stamp_provider = stamp.get("provider")
        action = STAMP_PROVIDER_TO_ACTION.get(stamp_provider)
        if action:
            objects_to_create.append(
                HumanPoints(address=address, action=action, tx_hash="")
            )

    # Bulk create all at once, let DB handle conflicts
    if objects_to_create:
        # sync_to_async needed - Django doesn't provide async bulk_create
        await sync_to_async(HumanPoints.objects.bulk_create)(
            objects_to_create, ignore_conflicts=True
        )


async def acheck_and_award_scoring_bonus(address: str, community_id: int) -> bool:
    """
    Check if user qualifies for scoring bonus (4+ passing scores)
    Returns True if bonus was newly awarded
    """
    # Check current passing scores count
    qualified_count = await HumanPointsCommunityQualifiedUsers.objects.filter(
        address=address
    ).acount()

    # Award bonus if qualified (let DB handle conflicts)
    if qualified_count >= 4:
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


def get_possible_points_data(multiplier: int) -> Dict:
    """
    Get user's total points with breakdown using raw SQL for efficiency.
    Returns total points, eligibility status, multiplier, and points breakdown.
    """
    possible_points_data_breakdown = {
        c.action: c.points for c in HumanPointsConfig.objects.all() if c.active
    }
    possible_points_data = {
        "total_points": 0,
        "breakdown": possible_points_data_breakdown,
        "is_eligible": False,
        "multiplier": multiplier,
    }
    return possible_points_data


async def acheck_and_award_misc_points(address: str):
    """
    Check and award miscellaneous points (MetaMask OG, etc.) for qualifying addresses.

    Args:
        address: The address to check for eligibility
    """
    # Award MetaMask OG points if on list (limit 5000)
    if settings.HUMAN_POINTS_MTA_ENABLED:
        try:
            mta_list = await AddressList.objects.aget(name="MetaMaskOG")
            # Check if address is on the list (case-insensitive)
            if await mta_list.addresses.filter(address=address.lower()).aexists():
                # Check if we've already awarded 5000 MetaMask OG points
                mta_count = await HumanPoints.objects.filter(
                    action=HumanPoints.Action.METAMASK_OG
                ).acount()

                if mta_count < 5000:
                    # Award MetaMask OG points (will create or get existing)
                    await HumanPoints.objects.aget_or_create(
                        address=address.lower(), action=HumanPoints.Action.METAMASK_OG
                    )
        except AddressList.DoesNotExist:
            # MetaMask OG list doesn't exist yet, skip MetaMask OG points
            pass
