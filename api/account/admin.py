from django.contrib import admin

from .models import Account, AccountAPIKey, Community


class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "address", "user")
    search_fields = ("address", "user__username")


class CommunityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "account")
    raw_id_fields = ("account", "scorer")
    search_fields = ("name", "description", "account__address")


class AccountAPIKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "prefix", "created", "expiry_date", "revoked")
    search_fields = ("id", "name", "prefix")


admin.site.register(Account, AccountAdmin)
admin.site.register(Community, CommunityAdmin)
admin.site.register(AccountAPIKey, AccountAPIKeyAdmin)
