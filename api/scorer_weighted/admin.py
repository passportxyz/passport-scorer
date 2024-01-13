from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin
from scorer_weighted.models import BinaryWeightedScorer, RescoreRequest, WeightedScorer


@admin.register(WeightedScorer)
class WeightedScorerAdmin(ScorerModelAdmin):
    list_display = ["id", "exclude_from_weight_updates"]
    list_filter = ["exclude_from_weight_updates"]


@admin.register(BinaryWeightedScorer)
class BinaryWeightedScorerAdmin(ScorerModelAdmin):
    list_display = [
        "id",
        "threshold",
        "exclude_from_weight_updates",
    ]
    list_filter = ["exclude_from_weight_updates"]


@admin.register(RescoreRequest)
class RescoreRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "created_at",
        "status",
        "num_communities_requested",
        "num_communities_processed",
        "updated_at",
    ]
    list_filter = ["created_at", "status"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "num_communities_requested",
        "num_communities_processed",
        "status",
    ]
    search_fields = ["id"]
    ordering = ["-created_at"]
