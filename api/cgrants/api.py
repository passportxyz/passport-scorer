# -*- coding: utf-8 -*-
"""
This file re-iplements the API endpoints from the original cgrants API: https://github.com/gitcoinco/web/blob/master/app/grants/views_api_vc.py

"""
from enum import Enum

import api_logging as logging
from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from ninja.security import APIKeyHeader
from ninja_extra import NinjaExtraAPI
from ninja_schema import Schema
from ninja_schema.orm.utils.converter import Decimal
from registry.api.v1 import is_valid_address
from registry.exceptions import InvalidAddressException

from .models import (
    Contribution,
    Grant,
    GrantContributionIndex,
    ProtocolContributions,
    RoundMapping,
    SquelchedAccounts,
    SquelchProfile,
)

logger = logging.getLogger(__name__)


api = NinjaExtraAPI(urls_namespace="cgrants")


class CgrantsApiKey(APIKeyHeader):
    param_name = "AUTHORIZATION"

    def authenticate(self, request, key):
        if key == settings.CGRANTS_API_TOKEN:
            return key


cg_api_key = CgrantsApiKey()


class ContributorStatistics(Schema):
    num_grants_contribute_to = int
    num_rounds_contribute_to = int
    total_contribution_amount = int
    num_gr14_contributions = int


class GranteeStatistics(Schema):
    num_owned_grants = int
    num_grant_contributors = int
    num_grants_in_eco_and_cause_rounds = int
    total_contribution_amount = int


class IdentifierType(Enum):
    HANDLE = "handle"
    GITHUB_ID = "github_id"


def _get_contributor_statistics_for_cgrants(address: str) -> dict:
    identifier_query = Q(contributor_address=address)

    contributions = GrantContributionIndex.objects.filter(
        identifier_query, contribution__success=True
    )

    if contributions.count() == 0:
        return {
            "num_grants_contribute_to": 0,
            "total_contribution_amount": 0,
        }

    # Get number of grants the user contributed to

    num_grants_contribute_to = (
        contributions.order_by("grant_id").values("grant_id").distinct().count()
    )

    # Get the total contribution amount
    total_contribution_amount = contributions.aggregate(
        total_contribution_amount=Sum("amount")
    )["total_contribution_amount"]

    if total_contribution_amount is None:
        total_contribution_amount = 0

    return {
        "num_grants_contribute_to": num_grants_contribute_to,
        "total_contribution_amount": total_contribution_amount,
    }


def _get_contributor_statistics_for_protocol(address: str) -> dict:
    # Get the round numbers where the address is squelched
    squelched_rounds = SquelchedAccounts.objects.filter(address=address).values_list(
        "round_number", flat=True
    )

    # Get round_eth_address for squelched round numbers
    squelched_round_ids = RoundMapping.objects.filter(
        round_number__in=squelched_rounds
    ).values_list("round_eth_address", flat=True)

    # Get contributions excluding squelched rounds
    protocol_filter = ProtocolContributions.objects.filter(
        contributor=address, amount__gte=0.95
    ).exclude(round__in=squelched_round_ids)

    # Calculate total amount and number of projects
    total_amount_usd = protocol_filter.aggregate(Sum("amount"))["amount__sum"] or 0
    num_projects = (
        protocol_filter.aggregate(Count("project", distinct=True))["project__count"]
        or 0
    )

    return {
        "num_grants_contribute_to": num_projects,
        "total_contribution_amount": round(total_amount_usd, 3),
    }


@api.get(
    "/contributor_statistics",
    response=ContributorStatistics,
    auth=cg_api_key,
)
def contributor_statistics(
    request, address: str | None = None, github_id: str | None = None
):
    if not address:
        return JsonResponse(
            {
                "error": "Bad request, 'address' is missing or invalid. A valid address is required."
            },
            status=400,
        )

    if not is_valid_address(address):
        raise InvalidAddressException()

    address = address.lower()

    cgrants_contributions = _get_contributor_statistics_for_cgrants(address)
    protocol_contributions = _get_contributor_statistics_for_protocol(address)

    combined_contributions = {
        key: float(
            round(
                (
                    protocol_contributions.get(key, 0)
                    + cgrants_contributions.get(key, 0)
                ),
                2,
            )
        )
        for key in set(protocol_contributions) | set(cgrants_contributions)
    }

    return JsonResponse(combined_contributions)


@api.get(
    "/allo/contributor_statistics",
    response=ContributorStatistics,
    auth=cg_api_key,
)
def allo_contributor_statistics(request, address: str | None = None):
    if not address:
        return JsonResponse(
            {"error": "Bad request, 'address' parameter is missing or invalid"},
            status=400,
        )

    if address:
        address = address.lower()

    response_for_protocol = _get_contributor_statistics_for_protocol(address)

    return JsonResponse(response_for_protocol)


def _get_grantee_statistics(identifier, identifier_type):
    if identifier_type == IdentifierType.HANDLE:
        grant_identifier_query = Q(admin_profile__handle=identifier)

        contribution_identifier_query = Q(
            subscription__grant__admin_profile__handle=identifier
        ) & ~Q(subscription__contributor_profile__handle=identifier)
    else:
        grant_identifier_query = Q(admin_profile__github_id=identifier)

        contribution_identifier_query = Q(
            subscription__grant__admin_profile__github_id=identifier
        ) & ~Q(subscription__contributor_profile__github_id=identifier)

    # Get number of owned grants
    num_owned_grants = Grant.objects.filter(
        grant_identifier_query, hidden=False, active=True, is_clr_eligible=True
    ).count()

    # Get the total amount of contrinutors for one users grants that where not squelched and are not the owner himself
    all_squelched = SquelchProfile.objects.filter(active=True).values_list(
        "profile_id", flat=True
    )

    num_grant_contributors = (
        Contribution.objects.filter(
            contribution_identifier_query,
            success=True,
            subscription__is_mainnet=True,
            subscription__grant__hidden=False,
            subscription__grant__active=True,
            subscription__grant__is_clr_eligible=True,
        )
        .exclude(subscription__contributor_profile_id__in=all_squelched)
        .order_by("subscription__contributor_profile_id")
        .values("subscription__contributor_profile_id")
        .distinct()
        .count()
    )

    # Get the total amount of contributions received by the owned grants (excluding the contributions made by the owner)
    total_contribution_amount = Contribution.objects.filter(
        contribution_identifier_query,
        success=True,
        subscription__is_mainnet=True,
        subscription__grant__hidden=False,
        subscription__grant__active=True,
        subscription__grant__is_clr_eligible=True,
    ).aggregate(Sum("amount_per_period_usdt"))["amount_per_period_usdt__sum"]
    total_contribution_amount = (
        total_contribution_amount if total_contribution_amount is not None else 0
    )

    # [IAM] As an IAM server, I want to issue stamps for grant owners whose project have tagged matching-eligibel in an eco-system and/or cause round
    num_grants_in_eco_and_cause_rounds = Grant.objects.filter(
        grant_identifier_query,
        hidden=False,
        active=True,
        is_clr_eligible=True,
        clr_calculations__grantclr__type__in=["ecosystem", "cause"],
    ).count()

    return JsonResponse(
        {
            "num_owned_grants": num_owned_grants,
            "num_grant_contributors": num_grant_contributors,
            "num_grants_in_eco_and_cause_rounds": num_grants_in_eco_and_cause_rounds,
            "total_contribution_amount": total_contribution_amount,
        }
    )


@api.get(
    "/grantee_statistics",
    response=GranteeStatistics,
    auth=cg_api_key,
)
def grantee_statistics(
    request, handle: str | None = None, github_id: str | None = None
):
    if not handle and not github_id:
        return JsonResponse(
            {
                "error": "Bad request, 'handle' and 'github_id' parameter is missing or invalid. Either one is required."
            },
            status=400,
        )

    if handle:
        return _get_grantee_statistics(handle, IdentifierType.HANDLE)
    else:
        return _get_grantee_statistics(github_id, IdentifierType.GITHUB_ID)
