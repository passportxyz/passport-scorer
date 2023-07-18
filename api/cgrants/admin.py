from django.contrib import admin

from .models import (
    Contribution,
    Grant,
    GrantCLR,
    GrantCLRCalculation,
    GrantContributionIndex,
    Profile,
    SquelchProfile,
    Subscription,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("handle",)
    search_fields = ("handle",)


@admin.register(Grant)
class GrantAdmin(admin.ModelAdmin):
    list_display = ("admin_profile", "hidden", "active", "is_clr_eligible")
    list_filter = ("hidden", "active", "is_clr_eligible")
    search_fields = ("admin_profile__handle",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("grant", "contributor_profile")
    search_fields = ("grant__admin_profile__handle", "contributor_profile__handle")


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ("subscription",)


@admin.register(GrantCLR)
class GrantCLRAdmin(admin.ModelAdmin):
    list_display = ("type",)
    list_filter = ("type",)


@admin.register(GrantCLRCalculation)
class GrantCLRCalculationAdmin(admin.ModelAdmin):
    list_display = ("active", "latest", "grant", "grantclr")
    list_filter = ("active", "latest")
    search_fields = ("grant__admin_profile__handle", "grantclr__type")


@admin.register(SquelchProfile)
class SquelchProfileAdmin(admin.ModelAdmin):
    list_display = ("profile", "active")
    list_filter = ("active",)
    search_fields = ("profile__handle",)


@admin.register(GrantContributionIndex)
class GrantContributionIndexAdmin(admin.ModelAdmin):
    list_display = ("profile", "contribution", "grant", "round_num", "amount")
    list_filter = ("round_num",)
    search_fields = ("profile__handle", "grant__admin_profile__handle")
