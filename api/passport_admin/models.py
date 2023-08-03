"""
Module for defining models for Passport Admin.
Includes models for PassportBanner and DismissedBanners.
"""

from django.db import models


class PassportBanner(models.Model):
    """
    Model representing a Passport Banner.
    """

    content = models.TextField()
    link = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)


class DismissedBanners(models.Model):
    """
    Model representing Dismissed Banners.
    """

    address = models.CharField(max_length=255)
    banner = models.ForeignKey(
        PassportBanner,
        on_delete=models.CASCADE,
        default=None,
        related_name="dismissedbanners",
    )
