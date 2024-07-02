from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin
from stake.models import Stake, StakeEvent, ReindexRequest


@admin.register(Stake)
class StakeAdmin(ScorerModelAdmin):
    list_display = [
        "id",
        "chain",
        "staker",
        "stakee",
        "lock_time",
        "unlock_time",
        "current_amount",
    ]

    list_filter = [
        "chain",
    ]

    search_fields = [
        "staker",
        "stakee",
    ]
    search_help_text = "Search by: " + ", ".join(search_fields)


@admin.register(StakeEvent)
class StakeEventAdmin(ScorerModelAdmin):
    list_display = [
        "id",
        "event_type",
        "staker",
        "stakee",
        "amount",
        "block_number",
        "tx_hash",
        "unlock_time",
    ]

    list_filter = [
        "chain",
        "event_type",
    ]

    search_fields = [
        "staker",
        "stakee",
        "block_number",
        "tx_hash",
    ]
    search_help_text = "Search by: " + ", ".join(search_fields)


@admin.register(ReindexRequest)
class ReindexRequestAdmin(admin.ModelAdmin):
    list_display = [
        "pending",
        "chain",
        "start_block_number",
        "created_at",
    ]

    list_filter = [
        "chain",
        "pending",
    ]

    readonly_fields = ("pending",)
