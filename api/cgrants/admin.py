from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin

from .models import (
    Contribution,
    Grant,
    GrantCLR,
    GrantCLRCalculation,
    GrantContributionIndex,
    Profile,
    ProtocolContributions,
    SquelchedAccounts,
    SquelchProfile,
    Subscription,
)


@admin.register(Profile)
class ProfileAdmin(ScorerModelAdmin):
    list_display = ("handle", "github_id")
    search_fields = ("handle", "github_id")


@admin.register(Grant)
class GrantAdmin(ScorerModelAdmin):
    list_display = ("admin_profile", "hidden", "active", "is_clr_eligible")
    list_filter = ("hidden", "active", "is_clr_eligible")
    search_fields = ("admin_profile__handle", "admin_profile__github_id")


@admin.register(Subscription)
class SubscriptionAdmin(ScorerModelAdmin):
    list_display = ("grant", "contributor_profile")
    search_fields = (
        "grant__admin_profile__handle",
        "contributor_profile__handle",
        "grant__admin_profile__github_id",
        "grant__admin_profile__github_id",
    )


@admin.register(Contribution)
class ContributionAdmin(ScorerModelAdmin):
    list_display = ("subscription",)


@admin.register(GrantCLR)
class GrantCLRAdmin(ScorerModelAdmin):
    list_display = ("type",)
    list_filter = ("type",)


@admin.register(GrantCLRCalculation)
class GrantCLRCalculationAdmin(ScorerModelAdmin):
    list_display = ("active", "latest", "grant", "grantclr")
    list_filter = ("active", "latest")
    search_fields = (
        "grant__admin_profile__handle",
        "grant__admin_profile__github_id",
        "grantclr__type",
    )


@admin.register(SquelchProfile)
class SquelchProfileAdmin(ScorerModelAdmin):
    list_display = ("profile", "active")
    list_filter = ("active",)
    search_fields = ("profile__handle", "profile__github_id")


@admin.register(SquelchedAccounts)
class SquelchedAccountsAdmin(ScorerModelAdmin):
    list_display = ("address", "score_when_squelched", "sybil_signal")
    search_fields = ("address", "score_when_squelched", "sybil_signal")


@admin.register(GrantContributionIndex)
class GrantContributionIndexAdmin(ScorerModelAdmin):
    list_display = ("profile", "contribution", "grant", "round_num", "amount")
    list_filter = ("round_num",)
    search_fields = (
        "profile__handle",
        "grant__admin_profile__handle",
        "profile__github_id",
        "grant__admin_profile__github_id",
    )


@admin.register(ProtocolContributions)
class ProtocolContributionsAdmin(ScorerModelAdmin):
    list_display = ("ext_id", "round", "contributor", "amount")
    list_filter = ("round",)
    search_fields = ("contributor", "round", "project")
