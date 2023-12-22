"""
Admin for the ceramic cache app
"""
from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin

from .models import CeramicCache


@admin.register(CeramicCache)
class CeramicCacheAdmin(ScorerModelAdmin):
    list_display = ("id", "address", "provider", "stamp")
    search_fields = ("address",)
    search_help_text = "This will perform a search by 'address'"
    show_full_result_count = False


class AccountAPIKeyAdmin(ScorerModelAdmin):
    list_display = ("id", "name", "prefix", "created", "expiry_date", "revoked")
    search_fields = ("id", "name", "prefix")
