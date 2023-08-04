# -*- coding: utf-8 -*-
"""
This file re-iplements the API endpoints from the original cgrants API: https://github.com/gitcoinco/web/blob/master/app/grants/views_api_vc.py

"""
import logging
from enum import Enum

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from ninja.security import APIKeyHeader
from ninja_extra import NinjaExtraAPI
from ninja_schema import Schema

from .models import (
    Contribution,
    Grant,
    GrantContributionIndex,
    ProtocolContributions,
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


def _get_contributor_statistics_for_cgrants(
    identifier: str, identifier_type: IdentifierType
) -> dict:
    if identifier_type == IdentifierType.HANDLE:
        identifier_query = Q(profile__handle=identifier)
    else:
        identifier_query = Q(profile__github_id=identifier)

    # Get number of grants the user contributed to

    num_grants_contribute_to = (
        GrantContributionIndex.objects.filter(identifier_query)
        .order_by("grant_id")
        .values("grant_id")
        .distinct()
        .count()
    )

    # Get number of rounds the user contributed to
    num_rounds_contribute_to = (
        GrantContributionIndex.objects.filter(identifier_query, round_num__isnull=False)
        .order_by("round_num")
        .values("round_num")
        .distinct()
        .count()
    )

    # Get the total contribution amount
    total_contribution_amount = GrantContributionIndex.objects.filter(
        identifier_query
    ).aggregate(total_contribution_amount=Sum("amount"))["total_contribution_amount"]

    if total_contribution_amount is None:
        total_contribution_amount = 0

    # GR14 contributor (and not squelched by FDD)
    profile_squelch = SquelchProfile.objects.filter(
        identifier_query, active=True
    ).values_list("profile_id", flat=True)

    num_gr14_contributions = (
        GrantContributionIndex.objects.filter(identifier_query, round_num=14)
        .exclude(profile_id__in=profile_squelch)
        .count()
    )

    return {
        "num_grants_contribute_to": num_grants_contribute_to,
        "num_rounds_contribute_to": num_rounds_contribute_to,
        "total_contribution_amount": total_contribution_amount,
        "num_gr14_contributions": num_gr14_contributions,
    }


def _get_contributor_statistics_for_protocol(address: str) -> dict:
    total_amount_usd = ProtocolContributions.objects.filter(
        contributor=address
    ).aggregate(Sum("amount"))["amount__sum"]
    num_rounds = ProtocolContributions.objects.filter(contributor=address).aggregate(
        Count("round", distinct=True)
    )["round__count"]
    num_projects = ProtocolContributions.objects.filter(contributor=address).aggregate(
        Count("project", distinct=True)
    )["project__count"]

    return {
        "num_grants_contribute_to": num_projects if num_projects is not None else 0,
        "num_rounds_contribute_to": num_rounds if num_rounds is not None else 0,
        "total_contribution_amount": total_amount_usd
        if total_amount_usd is not None
        else 0,
        "num_gr14_contributions": 0,
    }


@api.get(
    "/contributor_statistics",
    response=ContributorStatistics,
    auth=cg_api_key,
)
def contributor_statistics(
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
        response = _get_contributor_statistics_for_cgrants(
            handle, IdentifierType.HANDLE
        )
    else:
        response = _get_contributor_statistics_for_cgrants(
            github_id, IdentifierType.GITHUB_ID
        )

    return JsonResponse(response)


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
