from django.contrib import admin

from scorer.scorer_admin import ScorerModelAdmin
from data_model.models import Cache


@admin.register(Cache)
class CacheAdmin(ScorerModelAdmin):
    list_display = [
        "key_0",
        "key_1",
        "value",
        "updated_at",
    ]

    list_filter = []

    search_fields = [
        "key_0",
        "key_1",
        "value",
    ]
    search_help_text = "Search by: " + ", ".join(search_fields)
