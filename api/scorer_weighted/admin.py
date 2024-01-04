from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin
from scorer_weighted.models import BinaryWeightedScorer, WeightedScorer


@admin.register(WeightedScorer)
class WeightedScorerAdmin(ScorerModelAdmin):
    list_display = ["id", "exclude_from_weight_updates"]


@admin.register(BinaryWeightedScorer)
class BinaryWeightedScorerAdmin(ScorerModelAdmin):
    list_display = [
        "id",
        "threshold",
        "exclude_from_weight_updates",
    ]
