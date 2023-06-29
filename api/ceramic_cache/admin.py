"""
Admin for the ceramic cache app
"""
from django.contrib import admin

from .models import CeramicCache


class CeramicCacheAdmin(admin.ModelAdmin):
    list_display = ("id", "address", "provider", "stamp")
    search_fields = ("address",)
    search_help_text = "This will perform a search by 'address'"
    show_full_result_count = False


class AccountAPIKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "prefix", "created", "expiry_date", "revoked")
    search_fields = ("id", "name", "prefix")


admin.site.register(CeramicCache, CeramicCacheAdmin)
