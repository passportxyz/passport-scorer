"""
Admin for the ceramic cache app
"""

from django import forms
from django.contrib import admin, messages
from django.forms import ModelForm
from django.utils import timezone

from scorer.scorer_admin import ScorerModelAdmin

from .models import Ban, CeramicCache, Revocation


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
        "proof_value",
    )
    list_filter = ("deleted_at", "compose_db_save_status")
    search_fields = ("address__exact", "compose_db_stream_id__exact", "proof_value")
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


@admin.register(Revocation)
class RevocationAdmin(ScorerModelAdmin):
    list_display = ("id", "proof_value", "ceramic_cache")
    search_fields = ("proof_value",)


class BanForm(ModelForm):
    class Meta:
        model = Ban
        fields = ["hash", "address", "provider", "end_time", "reason"]
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "hash": "Specific credential hash to ban",
            "address": "Address to ban",
            "provider": "Provider (e.g. CoinbaseDualVerification) to ban - must be used with address",
            "end_time": "Leave blank for indefinite ban",
            "reason": "(Optional) THIS WILL BE PUBLICLY VISIBLE",
        }


@admin.action(description="Revoke matching credentials for selected bans")
def revoke_matching_credentials_action(modeladmin, request, queryset):
    success_count = 0
    error_count = 0

    for ban in queryset:
        try:
            ban.revoke_matching_credentials()
            success_count += 1
        except Exception as e:
            error_count += 1
            modeladmin.message_user(
                request,
                f"Error processing ban {ban.pk}: {str(e)}",
                level=messages.ERROR,
            )

    if success_count:
        modeladmin.message_user(
            request,
            f"Successfully processed {success_count} ban(s)",
            level=messages.SUCCESS,
        )

    if error_count:
        modeladmin.message_user(
            request,
            f"Failed to process {error_count} ban(s). See errors above.",
            level=messages.WARNING,
        )


@admin.register(Ban)
class BanAdmin(admin.ModelAdmin):
    form = BanForm
    list_display = [
        "get_ban_description",
        "is_active",
        "end_time",
        "matching_revoked",
        "created_at",
    ]
    actions = [revoke_matching_credentials_action]
    change_form_template = "ban/change_form.html"
    list_filter = ["created_at", "end_time"]
    search_fields = ["address", "hash", "provider", "reason"]
    readonly_fields = ["created_at", "last_run_revoke_matching"]

    @admin.display(description="Ban Condition")
    def get_ban_description(self, obj):
        parts = []
        if obj.hash:
            parts.append(f"hash={obj.hash}")
        if obj.address:
            parts.append(f"address={obj.address}")
        if obj.provider:
            parts.append(f"provider={obj.provider}")
        return "Ban if: " + " AND ".join(parts)

    @admin.display(boolean=True)
    def is_active(self, obj):
        if not obj.end_time:
            return True
        return obj.end_time > timezone.now()

    @admin.display(boolean=True)
    def matching_revoked(self, obj):
        return obj.last_run_revoke_matching is not None
