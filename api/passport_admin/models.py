"""
Module for defining models for Passport Admin.
Includes models for PassportBanner and DismissedBanners.
"""

from django.conf import settings
from django.db import models

from account.models import Community, EthAddressField

APPLICATION_CHOICES = [
    ("passport", "Passport"),
    ("id_staking_v2", "ID Staking V2"),
]


class PassportBanner(models.Model):
    """
    Model representing a Passport Banner.
    """

    content = models.TextField()
    link = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    application = models.CharField(
        max_length=50,
        choices=APPLICATION_CHOICES,
        default="passport",
        db_index=True,
    )


class DismissedBanners(models.Model):
    """
    Model representing Dismissed Banners.
    """

    address = EthAddressField()
    banner = models.ForeignKey(
        PassportBanner,
        on_delete=models.CASCADE,
        default=None,
        related_name="dismissedbanners",
    )


# Notifications
NOTIFICATION_TYPES = [
    ("custom", "Custom"),
    ("stamp_expiry", "Stamp Expiry"),
    ("on_chain_expiry", "OnChain Expiry"),
    ("deduplication", "Deduplication"),
]


def get_default_ceramic_cache_community():
    if not settings.CERAMIC_CACHE_SCORER_ID:
        return Community.objects.first().id
    else:
        return settings.CERAMIC_CACHE_SCORER_ID


class Notification(models.Model):
    """
    Model representing a Notification.
    """

    notification_id = models.CharField(
        max_length=255, unique=True
    )  # unique deterministic identifier for the notification

    type = models.CharField(
        max_length=50, choices=NOTIFICATION_TYPES, default="custom", db_index=True
    )
    is_active = models.BooleanField(default=False, db_index=True)

    link = models.CharField(max_length=255, null=True, blank=True)
    link_text = models.CharField(max_length=255, null=True, blank=True)
    content = models.TextField()
    created_at = models.DateField(auto_now_add=True, db_index=True)
    expires_at = models.DateField(null=True, blank=True, db_index=True)
    eth_address = EthAddressField(
        null=True, blank=True, db_index=True
    )  # account/ eth address for which the notification is created. If null then it is a global notification wgich will be shown to all users.
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="notifications",
        default=get_default_ceramic_cache_community,
    )


class NotificationStatus(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False, db_index=True)
    is_deleted = models.BooleanField(
        default=False, db_index=True
    )  # is dismissed => should not longer be shown to the user
    eth_address = EthAddressField(
        db_index=True
    )  # The account / eth address that dismissed the notification. Required to track the dismissed notifications / user in case of global notifications.


class LastScheduledRun(models.Model):
    name = models.CharField(
        max_length=255, unique=True, blank=False, null=False, db_index=True
    )
    last_run = models.DateTimeField(blank=False, null=False)


class SystemTestRun(models.Model):
    timestamp = models.DateTimeField(
        db_index=True, null=True, blank=True, auto_now_add=True
    )

    def __str__(self):
        return f"#{self.id} @{self.timestamp}"


# This table is written to directly (i.e. with pg) by the system tests
class SystemTestResult(models.Model):
    name = models.CharField(max_length=255, blank=False, null=False, db_index=True)
    category = models.JSONField(default=list)
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(db_index=True)
    run = models.ForeignKey(
        SystemTestRun, on_delete=models.PROTECT, related_name="results"
    )
