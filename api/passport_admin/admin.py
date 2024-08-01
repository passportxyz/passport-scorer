"""
Module for administering Passport Admin.
This includes registering the relevant models for PassportBanner and DismissedBanners.
"""

from django.contrib import admin

from scorer.scorer_admin import ScorerModelAdmin

from .models import (
    DismissedBanners,
    LastScheduledRun,
    Notification,
    NotificationStatus,
    PassportBanner,
)

admin.site.register(DismissedBanners)


@admin.register(PassportBanner)
class PassportAdmin(admin.ModelAdmin):
    """
    Admin class for PassportBanner.
    """

    list_display = ("content", "link", "is_active", "application")
    search_fields = ("content", "is_active", "link")
    list_filter = ("is_active", "application")


# ScorerModelAdmin
@admin.register(Notification)
class NotificationAdmin(ScorerModelAdmin):
    """
    Admin class for Notification.
    """

    list_display = ("notification_id", "type", "is_active", "eth_address")
    search_fields = ("eth_address", "type")
    list_filter = (
        "type",
        "eth_address",
        "is_active",
        "created_at",
        "expires_at",
        "link",
        "link_text",
    )


@admin.register(NotificationStatus)
class NotificationStatusAdmin(ScorerModelAdmin):
    """
    Admin class for NotificationStatus.
    """

    list_display = ("notification", "eth_address", "is_read", "is_deleted")
    search_fields = ("notification", "eth_address", "is_read", "is_deleted")
    list_filter = ("eth_address", "is_read", "is_deleted")


@admin.register(LastScheduledRun)
class LastScheduledRunAdmin(admin.ModelAdmin):
    """
    Admin class for LastScheduledRun.
    """

    list_display = ("name", "last_run")
    search_fields = ("name", "last_run")
    list_filter = ("name", "last_run")
