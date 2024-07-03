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
