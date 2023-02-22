from django.contrib import admin
from django.urls import reverse
from django.utils.html import mark_safe
from registry.models import Passport, Score, Stamp


class PassportAdmin(admin.ModelAdmin):
    list_display = ["address", "community_link"]
    search_fields = ["address"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related("community")
        return queryset

    @admin.display(description="Community")
    def community_link(self, obj):
        if obj.community:
            community = obj.community
            community_url = reverse(
                f"admin:{community._meta.app_label}_{community._meta.model_name}_change",
                args=(community.pk,),
            )
            display_text = f'<a href="{community_url}">{community.name}</a>'

            if display_text:
                return mark_safe(display_text)

        return "-"


PassportAdmin.community_link.verbose = "dddd"


class StampAdmin(admin.ModelAdmin):
    list_display = ["passport", "community", "provider", "hash"]
    search_fields = ["passport__address", "provider", "hash"]
    raw_id_fields = ["passport"]

    @admin.display(description="Community")
    def community(self, obj):
        if obj.passport and obj.passport.community:
            community = obj.passport.community
            community_url = reverse(
                f"admin:{community._meta.app_label}_{community._meta.model_name}_change",
                args=(community.pk,),
            )
            display_text = f'<a href="{community_url}">{community.name}</a>'

            if display_text:
                return mark_safe(display_text)

        return "-"

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

    @admin.display(description="Community")
    def community(self, obj):
        if obj.passport and obj.passport.community:
            community = obj.passport.community
            community_url = reverse(
                f"admin:{community._meta.app_label}_{community._meta.model_name}_change",
                args=(community.pk,),
            )
            display_text = f'<a href="{community_url}">{community.name}</a>'

            if display_text:
                return mark_safe(display_text)

        return "-"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related("passport__community")
        return queryset


admin.site.register(Passport, PassportAdmin)
admin.site.register(Stamp, StampAdmin)
admin.site.register(Score, ScoreAdmin)
