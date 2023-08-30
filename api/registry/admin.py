from django.contrib import admin
from registry.models import Event, HashScorerLink, Passport, Score, Stamp
from scorer.scorer_admin import ScorerModelAdmin


@admin.register(Passport)
class PassportAdmin(ScorerModelAdmin):
    list_display = ["address", "community"]
    search_fields = ["address"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("community")
        return queryset


@admin.register(Stamp)
class StampAdmin(ScorerModelAdmin):
    list_display = ["passport", "community", "provider", "hash"]
    search_fields = ["hash__exact"]
    search_help_text = "This will perform an exact case sensitive search by 'hash'"
    raw_id_fields = ["passport"]
    show_full_result_count = False

    def community(self, obj):
        return obj.passport.community

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("passport__community")
        return queryset


@admin.register(Score)
class ScoreAdmin(ScorerModelAdmin):
    list_display = [
        "passport",
        "community",
        "score",
        "last_score_timestamp",
        "status",
        "error",
    ]
    search_fields = ["passport__address", "status"]
    raw_id_fields = ["passport"]

    def community(self, obj):
        return obj.passport.community

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("passport__community")
        return queryset


@admin.register(Event)
class EventAdmin(ScorerModelAdmin):
    list_display = [
        "action",
        "created_at",
        "address",
        "data",
    ]

    list_filter = [
        "action",
    ]

    search_fields = [
        "created_at",
        "address",
        "data",
    ]


@admin.register(HashScorerLink)
class HashScorerLinkAdmin(ScorerModelAdmin):
    list_display = ["hash", "community", "address", "expires_at"]

    search_fields = [
        "hash",
        "community",
        "address",
    ]
