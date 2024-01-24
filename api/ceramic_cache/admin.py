"""
Admin for the ceramic cache app
"""
from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin

from .models import CeramicCache


@admin.register(CeramicCache)
class CeramicCacheAdmin(ScorerModelAdmin):
    list_display = (
        "id",
        "address",
        "provider",
        "stamp",
        "deleted_at",
        "compose_db_save_status",
        "compose_db_stream_id",
    )
    list_filter = ("deleted_at", "compose_db_save_status")
    search_fields = ("address", "compose_db_stream_id")
    search_help_text = (
        "This will perform a search by 'address' and 'compose_db_stream_id'"
    )
    show_full_result_count = False


class AccountAPIKeyAdmin(ScorerModelAdmin):
    list_display = ("id", "name", "prefix", "created", "expiry_date", "revoked")
    search_fields = ("id", "name", "prefix")
