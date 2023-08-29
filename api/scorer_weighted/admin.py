from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin
from scorer_weighted.models import BinaryWeightedScorer, Scorer, WeightedScorer

# Register your models here.


# @admin.register(Scorer)
class ScorerAdmin(ScorerModelAdmin):
    list_display = [
        "type",
        "id",
    ]


@admin.register(WeightedScorer)
class WeightedScorerAdmin(ScorerModelAdmin):
    list_display = ["id", "type"]


@admin.register(BinaryWeightedScorer)
class BinaryWeightedScorerAdmin(ScorerModelAdmin):
    list_display = ["id", "threshold", "type"]
