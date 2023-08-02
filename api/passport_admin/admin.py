"""
Module for administering Passport Admin.
This includes registering the relevant models for PassportBanner and DismissedBanners.
"""

from django.contrib import admin

from .models import DismissedBanners, PassportBanner

admin.site.register(PassportBanner)
admin.site.register(DismissedBanners)
