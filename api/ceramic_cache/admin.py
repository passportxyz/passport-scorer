"""
Admin for the ceramic cache app
"""

from django.contrib import admin, messages
from scorer.scorer_admin import ScorerModelAdmin

from .models import CeramicCache


@admin.action(
    description="Undeleted selected stamps", permissions=["rescore_individual_score"]
)
def undelete_selected_stamps(modeladmin, request, queryset):
    score_ids = [str(id) for id in queryset.values_list("id", flat=True)]
    undeleted_ids = []
    failed_to_undelete = []
    for c in CeramicCache.objects.filter(id__in=score_ids):
        try:
            if c.deleted_at:
                c.deleted_at = None
                c.save()
                undeleted_ids.append(c.id)
            else:
                failed_to_undelete.append(c.id)

        except Exception as e:
            failed_to_undelete.append(c.id)

    modeladmin.message_user(
        request,
        f"Have succesfully undeleted: {undeleted_ids}",
        level=messages.SUCCESS,
    )
    if failed_to_undelete:
        modeladmin.message_user(
            request,
            f"Failed to undelete: {failed_to_undelete}",
            level=messages.ERROR,
        )


@admin.register(CeramicCache)
class CeramicCacheAdmin(ScorerModelAdmin):
    list_display = (
        "id",
        "address",
        "provider",
        "stamp",
        "deleted_at",
        "compose_db_save_status",
        "compose_db_stream_id",
    )
    list_filter = ("deleted_at", "compose_db_save_status")
    search_fields = ("address__exact", "compose_db_stream_id__exact")
    search_help_text = (
        "This will perform a search by 'address' and 'compose_db_stream_id'"
    )

    actions = [undelete_selected_stamps]
    show_full_result_count = False

    def has_rescore_individual_score_permission(self, request):
        return request.user.has_perm("registry.rescore_individual_score")


class AccountAPIKeyAdmin(ScorerModelAdmin):
    list_display = ("id", "name", "prefix", "created", "expiry_date", "revoked")
    search_fields = ("id", "name", "prefix")
