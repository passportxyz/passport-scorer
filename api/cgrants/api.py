# -*- coding: utf-8 -*-
"""
This file re-iplements the API endpoints from the original cgrants API: https://github.com/gitcoinco/web/blob/master/app/grants/views_api_vc.py

"""
import logging
from datetime import datetime

from django.db.models import Sum
from django.http import JsonResponse
from ninja_extra import NinjaExtraAPI
from ninja_schema import Schema

from .models import Contribution, Grant, GrantContributionIndex, SquelchProfile

# from perftools.models import StaticJsonEnv

logger = logging.getLogger(__name__)


api = NinjaExtraAPI(urls_namespace="cgrants")

# def ami_api_token_required(func):
#     def decorator(request, *args, **kwargs):
#         try:
#             apiToken = StaticJsonEnv.objects.get(key="AMI_API_TOKEN")
#             expectedToken = apiToken.data["token"]
#             receivedToken = request.headers.get("Authorization")

#             if receivedToken:
#                 # Token shall look like "token <bearer token>", and we need only the <bearer token> part
#                 receivedToken = receivedToken.split(" ")[1]

#             if expectedToken == receivedToken:
#                 return func(request, *args, **kwargs)
#             else:
#                 return JsonResponse(
#                     {
#                         "error": "Access denied",
#                     },
#                     status=403,
#                 )
#         except Exception as e:
#             logger.error("Error in ami_api_token_required %s", e)
#             return JsonResponse(
#                 {
#                     "error": "An unexpected error occured",
#                 },
#                 status=500,
#             )

#     return decorator


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


# TODO add auth
@api.get("/contributor_statistics", response=ContributorStatistics)
def contributor_statistics(request):
    handle = request.GET.get("handle")

    if not handle:
        return JsonResponse(
            {"error": "Bad request, 'handle' parameter is missing or invalid"},
            status=400,
        )

    # Get number of grants the user contributed to
    num_grants_contribute_to = (
        GrantContributionIndex.objects.filter(profile__handle=handle)
        .order_by("grant_id")
        .distinct("grant_id")
        .count()
    )

    # Get number of rounds the user contributed to
    num_rounds_contribute_to = (
        GrantContributionIndex.objects.filter(
            profile__handle=handle, round_num__isnull=False
        )
        .order_by("round_num")
        .distinct("round_num")
        .count()
    )

    # Get the total contribution amount
    total_contribution_amount = GrantContributionIndex.objects.filter(
        profile__handle=handle
    ).aggregate(total_contribution_amount=Sum("amount"))["total_contribution_amount"]

    if total_contribution_amount is None:
        total_contribution_amount = 0

    # GR14 contributor (and not squelched by FDD)
    profile_squelch = SquelchProfile.objects.filter(
        profile__handle=handle, active=True
    ).values_list("profile_id", flat=True)

    num_gr14_contributions = (
        GrantContributionIndex.objects.filter(profile__handle=handle, round_num=14)
        .exclude(profile_id__in=profile_squelch)
        .count()
    )

    return JsonResponse(
        {
            "num_grants_contribute_to": num_grants_contribute_to,
            "num_rounds_contribute_to": num_rounds_contribute_to,
            "total_contribution_amount": total_contribution_amount,
            "num_gr14_contributions": num_gr14_contributions,
        }
    )


# TODO add auth
@api.get("/grantee_statistics", response=GranteeStatistics)
def grantee_statistics(request):
    handle = request.GET.get("handle")

    if not handle:
        return JsonResponse(
            {"error": "Bad request, 'handle' parameter is missing or invalid"},
            status=400,
        )

    # Get number of owned grants
    num_owned_grants = Grant.objects.filter(
        admin_profile__handle=handle,
        hidden=False,
        active=True,
        is_clr_eligible=True,
    ).count()

    # Get the total amount of contrinutors for one users grants that where not squelched and are not the owner himself
    all_squelched = SquelchProfile.objects.filter(active=True).values_list(
        "profile_id", flat=True
    )
    num_grant_contributors = (
        Contribution.objects.filter(
            success=True,
            subscription__network="mainnet",
            subscription__grant__hidden=False,
            subscription__grant__active=True,
            subscription__grant__is_clr_eligible=True,
            subscription__grant__admin_profile__handle=handle,
        )
        .exclude(subscription__contributor_profile_id__in=all_squelched)
        .exclude(subscription__contributor_profile__handle=handle)
        .order_by("subscription__contributor_profile_id")
        .distinct("subscription__contributor_profile_id")
        .count()
    )

    # Get the total amount of contributions received by the owned grants (excluding the contributions made by the owner)
    total_contribution_amount = (
        Contribution.objects.filter(
            success=True,
            subscription__network="mainnet",
            subscription__grant__hidden=False,
            subscription__grant__active=True,
            subscription__grant__is_clr_eligible=True,
            subscription__grant__admin_profile__handle=handle,
        )
        .exclude(subscription__contributor_profile__handle=handle)
        .aggregate(Sum("amount_per_period_usdt"))["amount_per_period_usdt__sum"]
    )
    total_contribution_amount = (
        total_contribution_amount if total_contribution_amount is not None else 0
    )

    # [IAM] As an IAM server, I want to issue stamps for grant owners whose project have tagged matching-eligibel in an eco-system and/or cause round
    num_grants_in_eco_and_cause_rounds = Grant.objects.filter(
        admin_profile__handle=handle,
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
