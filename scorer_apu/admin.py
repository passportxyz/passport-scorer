from django.contrib import admin

from scorer_apu.models import ApuScorer, Combo, NumInfo, Score

# Register your models here.


class ApuScorerAdmin(admin.ModelAdmin):
    list_display = ["start_time", "end_time", "accepted_providers"]


class ScoreAdmin(admin.ModelAdmin):
    list_display = ["passport", "scorer"]
    search_fields = ["passport__did"]


class ComboAdmin(admin.ModelAdmin):
    list_display = ["scorer", "passport", "combo", "count"]
    search_fields = ["passport__did"]


class NumInfoAdmin(admin.ModelAdmin):
    list_display = ["scorer", "stamp_count", "count"]


admin.site.register(ApuScorer, ApuScorerAdmin)
admin.site.register(Score, ScoreAdmin)
admin.site.register(Combo, ComboAdmin)
admin.site.register(NumInfo, NumInfoAdmin)
