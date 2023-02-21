"""
Admin for the ceramic cache app
"""
from django.contrib import admin

from .models import CeramicCache


class CeramicCacheAdmin(admin.ModelAdmin):
    list_display = ("id", "address", "provider", "stamp")
    search_fields = ("address", "provider", "stamp")


class AccountAPIKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "prefix", "created", "expiry_date", "revoked")
    search_fields = ("id", "name", "prefix")


admin.site.register(CeramicCache, CeramicCacheAdmin)
