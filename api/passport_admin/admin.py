"""
Module for administering Passport Admin.
This includes registering the relevant models for PassportBanner and DismissedBanners.
"""

from django.contrib import admin

from .models import DismissedBanners, PassportBanner

# admin.site.register(PassportBanner)
admin.site.register(DismissedBanners)


@admin.register(PassportBanner)
class PassportAdmin(admin.ModelAdmin):
    """
    Admin class for PassportBanner.
    """

    list_display = ("content", "link", "is_active", "application")
    search_fields = ("content", "is_active", "link")
    list_filter = ("is_active", "application")
