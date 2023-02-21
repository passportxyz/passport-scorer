from django.contrib import admin
from registry.models import Passport, Score, Stamp


class PassportAdmin(admin.ModelAdmin):
    list_display = ["address", "community"]
    search_fields = ["address"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related("community")
        return queryset


class StampAdmin(admin.ModelAdmin):
    list_display = ["passport", "community", "provider", "hash"]
    search_fields = ["passport__address", "provider", "hash"]
    raw_id_fields = ["passport"]

    def community(self, obj):
        return obj.passport.community

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related("passport__community")
        return queryset


class ScoreAdmin(admin.ModelAdmin):
    list_display = [
        "passport",
        "community",
        "score",
        "last_score_timestamp",
        "status",
        "error",
    ]
    search_fields = ["passport__address", "score", "status", "error"]
    raw_id_fields = ["passport"]

    def community(self, obj):
        return obj.passport.community

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related("passport__community")
        return queryset


admin.site.register(Passport, PassportAdmin)
admin.site.register(Stamp, StampAdmin)
admin.site.register(Score, ScoreAdmin)
