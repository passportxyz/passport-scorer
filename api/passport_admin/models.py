"""
Module for defining models for Passport Admin.
Includes models for PassportBanner and DismissedBanners.
"""

from account.models import EthAddressField
from django.db import models

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
        max_length=50, choices=APPLICATION_CHOICES, default="passport", db_index=True
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
NOTIFICATION_TYPEs = [
    ("custom", "Custom"),
    ("expiry", "Expiry"),
    ("deduplication", "Deduplication"),
]


class Notification(models.Model):
    """
    Model representing a Notification.
    """

    notification_id = models.CharField(
        unique=True
    )  # unique deterministic identifier for the notification

    type = models.CharField(
        max_length=50, choices=NOTIFICATION_TYPEs, default="custom", db_index=True
    )
    is_active = models.BooleanField(default=False)

    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateField(auto_now_add=True)
    expires_at = models.DateField()
    eth_address = models.CharField(
        max_length=255
    )  # account/ eth address for which the notification is created. If null then it is a global notification wgich will be shown to all users.
    # application = models.CharField(
    #     max_length=50, choices=APPLICATION_CHOICES, default="passport", db_index=True
    # )


class DismissedNotification(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    dismissed = models.BooleanField()
    eth_address = models.CharField(
        max_length=255
    )  # The account / eth address that dissmised the notification. Required to track the dismissed notifications / user in case of global notifications.
