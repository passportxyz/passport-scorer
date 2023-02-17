from django.contrib import admin
from registry.models import Passport, Score, Stamp


class PassportAdmin(admin.ModelAdmin):
    list_display = ["address"]
    search_fields = ["address"]
    raw_id_fields = ["community"]


class StampAdmin(admin.ModelAdmin):
    list_display = ["passport", "provider", "hash"]
    search_fields = ["passport__address", "provider", "hash"]
    raw_id_fields = ["passport"]


class ScoreAdmin(admin.ModelAdmin):
    list_display = ["passport", "score", "last_score_timestamp", "status", "error"]
    search_fields = ["passport__address", "score", "status", "error"]
    raw_id_fields = ["passport"]


admin.site.register(Passport, PassportAdmin)
admin.site.register(Stamp, StampAdmin)
admin.site.register(Score, ScoreAdmin)
