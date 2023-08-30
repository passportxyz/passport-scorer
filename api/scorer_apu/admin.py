from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin
from scorer_apu.models import ApuScorer, Combo, NumInfo

# Register your models here.


class ScoreAdmin(ScorerModelAdmin):
    list_display = ["passport", "scorer"]
    search_fields = ["passport__did"]


class ApuScorerAdmin(ScorerModelAdmin):
    list_display = ["start_time", "end_time", "accepted_providers"]


class ComboAdmin(ScorerModelAdmin):
    list_display = ["scorer", "passport", "combo", "count"]
    search_fields = ["passport__did"]


class NumInfoAdmin(ScorerModelAdmin):
    list_display = ["scorer", "stamp_count", "count"]


# admin.site.register(ApuScorer, ApuScorerAdmin)
# admin.site.register(Score, ScoreAdmin)
# admin.site.register(Combo, ComboAdmin)
# admin.site.register(NumInfo, NumInfoAdmin)
