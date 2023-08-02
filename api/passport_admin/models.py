from django.db import models

"""
Models for Passport Admin
"""


class PassportBanner(models.Model):
    """
    Passport Banner
    """

    title = models.CharField(max_length=255)
    description = models.TextField()
    link = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)


class DismissedBanners(models.Model):
    """
    Dismissed Banners
    """

    address = models.CharField(max_length=255)
    banner = models.ForeignKey(
        PassportBanner,
        on_delete=models.CASCADE,
        default=None,
        related_name="dismissedbanners",
    )
