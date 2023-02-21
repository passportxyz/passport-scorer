from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from rest_framework_api_key.admin import APIKeyAdmin
from scorer_weighted.models import Scorer

from .models import Account, AccountAPIKey, Community


class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "address", "user")
    search_fields = ("address", "user__username")
    raw_id_fields = ("user",)


class CommunityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "account", "scorer_link")
    raw_id_fields = ("account", "scorer")
    search_fields = ("name", "description", "account__address")
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

        return mark_safe(
            '<a href="{}">Scorer #{}</a>'.format(
                reverse(
                    "admin:%s_%s_change" % (category, field),
                    args=[obj.get_scorer().pk],
                ),
                obj.scorer.id,
            )
        )

    scorer_link.short_description = "Scorer Link"


class AccountAPIKeyAdmin(APIKeyAdmin):
    raw_id_fields = ("account",)
    pass


admin.site.register(Account, AccountAdmin)
admin.site.register(Community, CommunityAdmin)
admin.site.register(AccountAPIKey, AccountAPIKeyAdmin)
