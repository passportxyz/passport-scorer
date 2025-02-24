# -*- coding: utf-8 -*-
"""
This file re-iplements the API endpoints from the original cgrants API: https://github.com/gitcoinco/web/blob/master/app/grants/views_api_vc.py

"""

from enum import Enum

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from ninja.security import APIKeyHeader
from ninja_extra import NinjaExtraAPI
from ninja_schema import Schema
from ninja_schema.orm.utils.converter import Decimal
from pydantic import Field

import api_logging as logging
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
    num_grants_contribute_to: int = Field()
    num_rounds_contribute_to: int = Field()
    total_contribution_amount: int = Field()
    num_gr14_contributions: int = Field()


class GranteeStatistics(Schema):
    num_owned_grants: int = Field()
    num_grant_contributors: int = Field()
    num_grants_in_eco_and_cause_rounds: int = Field()
    total_contribution_amount: int = Field()


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


# TODO 3280 Remove this endpoint
@api.get(
    "/contributor_statistics",
    response=ContributorStatistics,
    auth=cg_api_key,
)
def contributor_statistics(request, address: str):
    return handle_get_contributor_statistics(address)


def handle_get_contributor_statistics(address: str):
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
