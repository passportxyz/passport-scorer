from django.contrib import admin
from scorer_weighted.models import WeightedScorer, BinaryWeightedScorer, Scorer

# Register your models here.


# @admin.register(Scorer)
class ScorerAdmin(admin.ModelAdmin):
    list_display = [
        "type",
        "id",
    ]


@admin.register(WeightedScorer)
class WeightedScorerAdmin(admin.ModelAdmin):
    list_display = ["id", "type"]


@admin.register(BinaryWeightedScorer)
class BinaryWeightedScorerAdmin(admin.ModelAdmin):
    list_display = ["id", "threshold", "type"]
