from django.contrib import admin
from scorer_weighted.models import WeightedScorer

# Register your models here.


class WeightedScorerAdmin(admin.ModelAdmin):
    list_display = ["start_time", "end_time", "weights"]


class ScoreAdmin(admin.ModelAdmin):
    list_display = ["passport", "scorer"]
    search_fields = ["passport__did"]


# admin.site.register(WeightedScorer, WeightedScorerAdmin)
# admin.site.register(Score, ScoreAdmin)
