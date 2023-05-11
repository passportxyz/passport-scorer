from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from rest_framework_api_key.admin import APIKeyAdmin
from scorer_weighted.models import Scorer

from .models import Account, AccountAPIKey, Community, RateLimits


class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "address", "user")
    search_fields = ("address", "user__username")
    raw_id_fields = ("user",)


class CommunityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "created_at",
        "description",
        "account",
        "scorer_link",
        "use_case",
        "deleted_at",
    )
    raw_id_fields = ("account", "scorer")
    search_fields = (
        "name",
        "description",
        "account__address",
        "created_at",
        "deleted_at",
    )
    readonly_fields = ("scorer_link",)

    def scorer_link(self, obj):
        # To add additional scorer types, just look at the URL on_delete
        # the edit page for the scorer type to get the category and field
        match obj.scorer.type:
            case Scorer.Type.WEIGHTED:
                category = "scorer_weighted"
                field = "weightedscorer"
            case Scorer.Type.WEIGHTED_BINARY | _:
                category = "scorer_weighted"
                field = "binaryweightedscorer"

        href = reverse(
            f"admin:{category}_{field}_change",
            args=[obj.get_scorer().pk],
        )
        return mark_safe(f'<a href="{href}">Scorer #{obj.scorer.id}</a>')

    scorer_link.short_description = "Scorer Link"


class AccountAPIKeyAdmin(APIKeyAdmin):
    raw_id_fields = ("account",)
    search_fields = (
        "id",
        "name",
        "prefix",
        "rate_limit",
        "account__user__username",
        "account__address",
    )

    list_display = (
        "name",
        "account",
        "rate_limit_display",
        "created",
        "revoked",
    )

    # Step 1: Define the edit action function
    def edit_selected(modeladmin, request, queryset):
        if queryset.count() != 1:
            modeladmin.message_user(
                request, "Please select exactly one row to edit.", level=messages.ERROR
            )
            return

        selected_instance = queryset.first()
        return HttpResponseRedirect(
            reverse(
                f"admin:{selected_instance._meta.app_label}_{selected_instance._meta.model_name}_change",
                args=(selected_instance.id,),
            )
        )

    # Step 3: Customize the action's display name in the dropdown menu
    edit_selected.short_description = "Edit selected row"

    # Step 2: Register the edit action
    actions = [edit_selected]


class APIKeyPermissionsAdmin(admin.ModelAdmin):
    list_display = ("id", "submit_passports", "read_scores", "create_scorers")


admin.site.register(Account, AccountAdmin)
admin.site.register(Community, CommunityAdmin)
admin.site.register(AccountAPIKey, AccountAPIKeyAdmin)
